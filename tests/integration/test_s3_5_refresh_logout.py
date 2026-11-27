"""Section 3.5: refresh rotation, reuse detection, logout and logout-all."""

import asyncio
import logging
import uuid
from collections.abc import AsyncIterator
from datetime import timedelta
from typing import Any, NoReturn

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import select, update
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, AsyncSession

from app.core import clock, security
from app.core.config import AuthSettings
from app.core.logging import JsonFormatter
from app.main import create_app
from app.models import AuditLog, RevokeReason, User, UserSession, UserStatus
from app.repositories import SessionRepository
from tests.api import WHOAMI, api_client, whoami_router
from tests.db import SERVICES, UNREACHABLE_DB, committed_user, service_database_settings
from tests.helpers import check_ok, client_for, make_settings

pytestmark = SERVICES
SIGNUP, LOGIN = "/api/v1/auth/signup", "/api/v1/auth/login"
REFRESH, LOGOUT, LOGOUT_ALL = (
    "/api/v1/auth/refresh",
    "/api/v1/auth/logout",
    "/api/v1/auth/logout-all",
)
PASSWORD = "Correct-Horse-Battery-9"


def _bearer(tokens: dict[str, Any]) -> dict[str, str]:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


async def _new_account(http: AsyncClient) -> tuple[str, dict[str, Any]]:
    email = f"user-{uuid.uuid4().hex[:12]}@example.com"
    assert (await http.post(SIGNUP, json={"email": email, "password": PASSWORD})).status_code == 202
    response = await http.post(LOGIN, json={"email": email, "password": PASSWORD})
    assert response.status_code == 200
    tokens: dict[str, Any] = response.json()
    return email, tokens


async def _refresh(http: AsyncClient, token: str) -> Response:
    return await http.post(REFRESH, json={"refresh_token": token})


async def _rows(db: AsyncSession, family_id: uuid.UUID | None = None) -> list[UserSession]:
    db.expunge_all()
    statement = select(UserSession).order_by(UserSession.created_at, UserSession.id)
    if family_id is not None:
        statement = statement.where(UserSession.family_id == family_id)
    return list((await db.execute(statement)).scalars())


async def test_s3_5_01_refresh_rotates_within_the_same_family(
    db: AsyncSession, db_connection: AsyncConnection
) -> None:
    async with api_client(db_connection, whoami_router) as http:
        _, first = await _new_account(http)
        response = await _refresh(http, first["refresh_token"])
        assert response.status_code == 200
        second = response.json()
        whoami = await http.get(WHOAMI, headers=_bearer(second))
    assert second["refresh_token"] != first["refresh_token"]
    assert second["access_token"] != first["access_token"]
    family = uuid.UUID(whoami.json()["session"])
    rows = await _rows(db, family)
    assert [r.revoked_reason for r in rows] == [RevokeReason.ROTATED, None]
    assert rows[1].token_hash == security.hash_token(second["refresh_token"])
    assert rows[0].family_started_at == rows[1].family_started_at


async def test_s3_5_02_replaying_a_rotated_token_revokes_the_whole_family(
    db: AsyncSession, db_connection: AsyncConnection
) -> None:
    async with api_client(db_connection, whoami_router) as http:
        _, stolen = await _new_account(http)
        legit = (await _refresh(http, stolen["refresh_token"])).json()
        family = uuid.UUID((await http.get(WHOAMI, headers=_bearer(legit))).json()["session"])
        replay = await _refresh(http, stolen["refresh_token"])  # the attacker's copy
        after_legit = await _refresh(http, legit["refresh_token"])
        access_after = await http.get(WHOAMI, headers=_bearer(legit))
    assert (replay.status_code, replay.json()["code"]) == (401, "auth.invalid_token")
    assert after_legit.status_code == 401  # the holder's newer token is dead too
    assert access_after.status_code == 401  # and so is the access token, at once
    rows = await _rows(db, family)
    assert {r.revoked_reason for r in rows} == {RevokeReason.ROTATED, RevokeReason.REUSE_DETECTED}
    assert all(r.revoked_at is not None for r in rows)
    reuse = await db.execute(select(AuditLog).where(AuditLog.action == "auth.refresh_token_reused"))
    entry = reuse.scalar_one()
    assert (entry.target_type, entry.target_id) == ("session", str(family))


@pytest.mark.parametrize("case", ["unknown", "expired", "logged_out"])
async def test_s3_5_03_dead_tokens_are_refused_without_revoking_anything(
    db: AsyncSession, db_connection: AsyncConnection, case: str
) -> None:
    async with api_client(db_connection) as http:
        _, tokens = await _new_account(http)
        token = tokens["refresh_token"]
        if case == "unknown":
            token = security.new_opaque_token()
        if case == "expired":
            await db.execute(update(UserSession).values(expires_at=clock.now()))
        if case == "logged_out":
            await http.post(LOGOUT, headers=_bearer(tokens))
        before = [(r.id, r.revoked_reason) for r in await _rows(db)]
        response = await _refresh(http, token)
    assert (response.status_code, response.json()["code"]) == (401, "auth.invalid_token")
    assert [(r.id, r.revoked_reason) for r in await _rows(db)] == before


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"refresh_token": ""},
        {"refresh_token": "x" * 513},
        {"refresh_token": 123},
        {"token": "x"},
    ],
)
async def test_s3_5_04_malformed_refresh_requests_are_422(
    db_connection: AsyncConnection, body: dict[str, object]
) -> None:
    async with api_client(db_connection) as http:
        response = await http.post(REFRESH, json=body)
    assert (response.status_code, response.json()["code"]) == (422, "request.validation_failed")


@pytest.fixture
async def committed_login(db_engine: AsyncEngine) -> AsyncIterator[str]:
    """A real login (several connections needed); everything removed after."""
    async with committed_user(db_engine, await security.hash_password(PASSWORD)) as email:
        yield email


async def test_s3_5_05_two_refreshes_racing_with_one_token_cannot_both_win(
    db_engine: AsyncEngine, committed_login: str
) -> None:
    settings = make_settings(database=service_database_settings(pool_size=5, max_overflow=5))
    app = create_app(settings, health_checks={"database": check_ok})
    async with app.router.lifespan_context(app), client_for(app) as http:
        login = await http.post(LOGIN, json={"email": committed_login, "password": PASSWORD})
        token = login.json()["refresh_token"]
        results = await asyncio.gather(_refresh(http, token), _refresh(http, token))
    assert sorted(r.status_code for r in results) == [200, 401]
    async with AsyncSession(db_engine) as session:
        user_id = (
            await session.execute(select(User.id).where(User.email == committed_login))
        ).scalar_one()
        rows = await session.execute(select(UserSession).where(UserSession.user_id == user_id))
        active = [r for r in rows.scalars() if r.revoked_at is None]
    assert active == []  # the loser looked like a replay: the family is revoked


async def test_s3_5_06_refresh_token_expires_exactly_on_time(
    db: AsyncSession, db_connection: AsyncConnection, monkeypatch: pytest.MonkeyPatch
) -> None:
    start = clock.now()
    now = [start]
    monkeypatch.setattr(clock, "now", lambda: now[0])
    async with api_client(db_connection) as http:
        _, tokens = await _new_account(http)
        ttl = timedelta(seconds=tokens["refresh_expires_in"])
        now[0] = start + ttl - timedelta(seconds=1)
        early = await _refresh(http, tokens["refresh_token"])
        now[0] = now[0] + ttl  # the new token's own end
        late = await _refresh(http, early.json()["refresh_token"])
    assert (early.status_code, late.status_code) == (200, 401)


async def test_s3_5_07_refreshing_cannot_extend_a_session_past_its_maximum_age(
    db_connection: AsyncConnection, monkeypatch: pytest.MonkeyPatch
) -> None:
    start = clock.now()
    now = [start]
    monkeypatch.setattr(clock, "now", lambda: now[0])
    policy = AuthSettings(refresh_ttl=timedelta(days=10), session_max_age=timedelta(days=15))
    async with api_client(db_connection, auth=policy) as http:
        _, tokens = await _new_account(http)
        now[0] = start + timedelta(days=9)
        second = await _refresh(http, tokens["refresh_token"])
        assert second.json()["refresh_expires_in"] == 6 * 24 * 3600  # capped at day 15, not 19
        now[0] = start + timedelta(days=15)
        beyond = await _refresh(http, second.json()["refresh_token"])
    assert beyond.status_code == 401


async def test_s3_5_08_logout_ends_the_session_at_once(
    db: AsyncSession, db_connection: AsyncConnection
) -> None:
    async with api_client(db_connection, whoami_router) as http:
        _, tokens = await _new_account(http)
        family = uuid.UUID((await http.get(WHOAMI, headers=_bearer(tokens))).json()["session"])
        response = await http.post(LOGOUT, headers=_bearer(tokens))
        access = await http.get(WHOAMI, headers=_bearer(tokens))
        refresh = await _refresh(http, tokens["refresh_token"])
    assert response.status_code == 204
    assert (access.status_code, refresh.status_code) == (401, 401)
    assert [r.revoked_reason for r in await _rows(db, family)] == [RevokeReason.LOGOUT]


async def test_s3_5_09_logging_out_twice_changes_nothing_more(
    db: AsyncSession, db_connection: AsyncConnection
) -> None:
    async with api_client(db_connection) as http:
        _, tokens = await _new_account(http)
        first = await http.post(LOGOUT, headers=_bearer(tokens))
        before = [(r.id, r.revoked_at) for r in await _rows(db)]
        second = await http.post(LOGOUT, headers=_bearer(tokens))
    assert (first.status_code, second.status_code) == (204, 401)
    assert [(r.id, r.revoked_at) for r in await _rows(db)] == before


async def test_s3_5_10_logout_all_ends_every_session_of_that_user_only(
    db: AsyncSession, db_connection: AsyncConnection
) -> None:
    async with api_client(db_connection) as http:
        email, phone = await _new_account(http)
        laptop = (await http.post(LOGIN, json={"email": email, "password": PASSWORD})).json()
        _, someone_else = await _new_account(http)
        response = await http.post(
            LOGOUT_ALL, json={"current_password": PASSWORD}, headers=_bearer(laptop)
        )
        phone_after = await _refresh(http, phone["refresh_token"])
        other_after = await _refresh(http, someone_else["refresh_token"])
    assert response.status_code == 204
    assert (phone_after.status_code, other_after.status_code) == (401, 200)
    reasons = [r.revoked_reason for r in await _rows(db)]
    assert reasons.count(RevokeReason.LOGOUT_ALL) == 2


@pytest.mark.parametrize("path", [LOGOUT, LOGOUT_ALL])
async def test_s3_5_11_logout_needs_a_token(db_connection: AsyncConnection, path: str) -> None:
    async with api_client(db_connection) as http:
        response = await http.post(path)
    assert (response.status_code, response.json()["code"]) == (401, "auth.not_authenticated")


async def test_s3_5_12_disabled_user_cannot_refresh(
    db: AsyncSession, db_connection: AsyncConnection
) -> None:
    async with api_client(db_connection) as http:
        email, tokens = await _new_account(http)
        await db.execute(update(User).where(User.email == email).values(status=UserStatus.DISABLED))
        count_before = len(await _rows(db))
        response = await _refresh(http, tokens["refresh_token"])
    assert response.status_code == 401
    assert len(await _rows(db)) == count_before  # no new session


async def test_s3_5_15_database_down_at_refresh_is_a_generic_500(
    caplog: pytest.LogCaptureFixture,
) -> None:
    app = create_app(make_settings(database=UNREACHABLE_DB), health_checks={"database": check_ok})
    refresh_token = security.new_opaque_token()
    with caplog.at_level(logging.INFO):
        async with app.router.lifespan_context(app), client_for(app) as http:
            response = await http.post(REFRESH, json={"refresh_token": refresh_token})
    assert response.status_code == 500
    logged = "\n".join(JsonFormatter().format(r) for r in caplog.records)
    assert refresh_token not in logged
    assert refresh_token not in response.text


def _lost_connection(*_: object, **__: object) -> NoReturn:
    raise OperationalError("UPDATE sessions", {}, ConnectionResetError("connection lost"))


@pytest.mark.parametrize(
    ("path", "method"), [(LOGOUT, "revoke_family"), (LOGOUT_ALL, "revoke_all")]
)
async def test_s3_5_16_database_failing_inside_logout_is_a_500_and_changes_nothing(
    db: AsyncSession,
    db_connection: AsyncConnection,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    path: str,
    method: str,
) -> None:
    async with api_client(db_connection) as http:
        _, tokens = await _new_account(http)
        monkeypatch.setattr(SessionRepository, method, _lost_connection)
        with caplog.at_level(logging.INFO):
            response = await http.post(
                path, json={"current_password": PASSWORD}, headers=_bearer(tokens)
            )
        monkeypatch.undo()
        still_in = await http.get("/api/v1/me", headers=_bearer(tokens))
    assert (response.status_code, still_in.status_code) == (500, 200)
    logged = "\n".join(JsonFormatter().format(r) for r in caplog.records)
    assert tokens["access_token"] not in logged


async def test_s3_5_17_default_limits_are_asvs_level_2_at_the_boundaries(
    db_connection: AsyncConnection, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Defaults: 30 minutes idle and 12 hours absolute (ASVS V3.3.2, level 2)."""
    start = clock.now()
    now = [start]
    monkeypatch.setattr(clock, "now", lambda: now[0])
    async with api_client(db_connection) as http:
        _, tokens = await _new_account(http)
        _, idle_ok = await _new_account(http)
        _, idle_out = await _new_account(http)
        token = tokens["refresh_token"]
        for _ in range(24):  # active use: a refresh every 29 minutes keeps it alive...
            now[0] += timedelta(minutes=29)
            response = await _refresh(http, token)
            assert response.status_code == 200, now[0] - start
            token = response.json()["refresh_token"]
        assert now[0] - start == timedelta(hours=11, minutes=36)
        now[0] = start + timedelta(hours=12) - timedelta(seconds=1)
        last = await _refresh(http, token)  # ...up to the last second of the 12 hours...
        now[0] = start + timedelta(hours=12)
        too_old = await _refresh(http, last.json()["refresh_token"])  # ...and not at 12 h
        access_at_12h = await http.get("/api/v1/me", headers=_bearer(last.json()))
        now[0] = start + timedelta(minutes=30) - timedelta(seconds=1)
        not_idle = await _refresh(http, idle_ok["refresh_token"])  # 30 min idle: 1 s early
        now[0] = start + timedelta(minutes=30)
        too_idle = await _refresh(http, idle_out["refresh_token"])  # exactly 30 min idle
    assert (last.status_code, too_old.status_code, access_at_12h.status_code) == (200, 401, 401)
    assert (not_idle.status_code, too_idle.status_code) == (200, 401)


async def test_s3_5_18_a_failed_rotation_leaves_the_old_token_working(
    db_connection: AsyncConnection, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The old row is marked rotated before the new one is written. Here the database
    refuses the new row itself (it violates `expires_after_created` at flush): the mark is
    rolled back with it, so the client can simply retry."""
    add = SessionRepository.add

    def broken_add(self: SessionRepository, row: UserSession) -> None:
        row.expires_at = row.created_at  # the INSERT fails a CHECK in the database
        add(self, row)

    async with api_client(db_connection) as http:
        _, tokens = await _new_account(http)
        monkeypatch.setattr(SessionRepository, "add", broken_add)
        failed = await _refresh(http, tokens["refresh_token"])
        monkeypatch.undo()
        retried = await _refresh(http, tokens["refresh_token"])
    assert (failed.status_code, retried.status_code) == (500, 200)


async def test_s3_5_19_a_refresh_on_a_node_whose_clock_is_behind_still_works(
    db_connection: AsyncConnection, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Behind a load balancer the refreshing node's clock may trail the login node's."""
    start = clock.now()
    now = [start]
    monkeypatch.setattr(clock, "now", lambda: now[0])
    async with api_client(db_connection) as http:
        _, tokens = await _new_account(http)
        now[0] = start - timedelta(seconds=2)
        response = await _refresh(http, tokens["refresh_token"])
    assert response.status_code == 200
