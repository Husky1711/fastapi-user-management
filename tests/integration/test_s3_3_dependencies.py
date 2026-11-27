"""Section 3.3: `get_current_user` and `client_info`, through a test-only route."""

import json
import logging
import uuid
from datetime import timedelta

import pytest
from fastapi import APIRouter
from sqlalchemy import event, update
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

from app.core import clock
from app.core.deps import Authenticated, Client
from app.core.logging import JsonFormatter
from app.core.security import issue_access_token
from app.main import create_app
from app.models import RevokeReason, User, UserSession, UserStatus
from tests.api import api_client, signed_in
from tests.db import SERVICES, UNREACHABLE_DB
from tests.helpers import check_ok, client_for, make_settings

pytestmark = SERVICES
WHOAMI = "/api/v1/_test/whoami"

router = APIRouter()


@router.get("/_test/whoami")
async def whoami(current: Authenticated, client: Client) -> dict[str, str | None]:
    return {
        "user": str(current.user.id),
        "email": current.user.email,
        "session": str(current.session_id),
        "ip": client.ip,
        "user_agent": client.user_agent,
    }


async def test_s3_3_01_valid_token_loads_the_user_and_session(
    db: AsyncSession, db_connection: AsyncConnection
) -> None:
    me = await signed_in(db)
    async with api_client(db_connection, router) as http:
        response = await http.get(WHOAMI, headers=me.headers)
    assert response.status_code == 200
    body = response.json()
    assert (body["user"], body["session"]) == (str(me.user.id), str(me.session.family_id))


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"Authorization": "Basic dXNlcjpwYXNz"},
        {"Authorization": "Bearer "},
        {"Authorization": "Bearer"},
    ],
)
async def test_s3_3_02_missing_credentials_are_not_authenticated(
    db_connection: AsyncConnection, headers: dict[str, str]
) -> None:
    async with api_client(db_connection, router) as http:
        response = await http.get(WHOAMI, headers=headers)
    assert response.status_code == 401
    assert response.json()["code"] == "auth.not_authenticated"
    assert response.headers["www-authenticate"] == "Bearer"
    assert response.headers["content-type"] == "application/problem+json"


async def _rejected_with_invalid_token(
    db_connection: AsyncConnection, token: str
) -> dict[str, object]:
    async with api_client(db_connection, router) as http:
        response = await http.get(WHOAMI, headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == 'Bearer error="invalid_token"'
    body: dict[str, object] = response.json()
    assert body["code"] == "auth.invalid_token"
    return body


async def test_s3_3_03_expired_forged_or_malformed_tokens_look_the_same(
    db: AsyncSession, db_connection: AsyncConnection
) -> None:
    me = await signed_in(db)
    settings = make_settings().jwt
    long_ago = clock.now() - timedelta(hours=2)
    expired, _ = issue_access_token(
        settings, user_id=me.user.id, session_id=me.session.family_id, now=long_ago
    )
    forged = me.access_token[:-4] + ("AAAA" if not me.access_token.endswith("AAAA") else "BBBB")
    bodies = [
        await _rejected_with_invalid_token(db_connection, token)
        for token in (expired, forged, "not-a-jwt", "a.b.c")
    ]
    assert len({(b["detail"], b["title"]) for b in bodies}) == 1  # nothing tells them apart


@pytest.mark.parametrize("ended", ["revoked", "expired"])
async def test_s3_3_04_token_of_an_ended_session_is_refused(
    db: AsyncSession, db_connection: AsyncConnection, ended: str
) -> None:
    me = await signed_in(db)
    values: dict[str, object] = (
        {"revoked_at": clock.now(), "revoked_reason": RevokeReason.LOGOUT}
        if ended == "revoked"
        else {
            "expires_at": clock.now() - timedelta(seconds=1),
            "created_at": clock.now() - timedelta(days=1),
            "family_started_at": clock.now() - timedelta(days=1),
        }
    )
    await db.execute(update(UserSession).where(UserSession.id == me.session.id).values(**values))
    await _rejected_with_invalid_token(db_connection, me.access_token)


@pytest.mark.parametrize("state", ["disabled", "deleted", "missing"])
async def test_s3_3_05_token_of_an_inactive_or_missing_user_is_refused(
    db: AsyncSession, db_connection: AsyncConnection, state: str
) -> None:
    me = await signed_in(db)
    if state == "disabled":
        await db.execute(
            update(User).where(User.id == me.user.id).values(status=UserStatus.DISABLED)
        )
    elif state == "deleted":
        await db.execute(
            update(User)
            .where(User.id == me.user.id)
            .values(status=UserStatus.DELETED, deleted_at=clock.now())
        )
    token = me.access_token
    if state == "missing":
        token, _ = issue_access_token(
            make_settings().jwt,
            user_id=uuid.uuid4(),
            session_id=me.session.family_id,
            now=clock.now(),
        )
    await _rejected_with_invalid_token(db_connection, token)


async def test_s3_3_06_session_of_another_user_is_refused(
    db: AsyncSession, db_connection: AsyncConnection
) -> None:
    me, other = await signed_in(db), await signed_in(db)
    borrowed, _ = issue_access_token(
        make_settings().jwt, user_id=me.user.id, session_id=other.session.family_id, now=clock.now()
    )
    await _rejected_with_invalid_token(db_connection, borrowed)


async def test_s3_3_07_refresh_token_is_not_an_access_token(
    db: AsyncSession, db_connection: AsyncConnection
) -> None:
    me = await signed_in(db)
    await _rejected_with_invalid_token(db_connection, me.refresh_token)


async def test_s3_3_08_client_info_from_the_connection_and_user_agent(
    db: AsyncSession, db_connection: AsyncConnection
) -> None:
    me = await signed_in(db)
    async with api_client(db_connection, router) as http:
        long_agent = await http.get(WHOAMI, headers=me.headers | {"User-Agent": "u" * 400})
        no_agent = await http.get(WHOAMI, headers=me.headers | {"User-Agent": ""})
    assert long_agent.json()["ip"] == "127.0.0.1"  # the test transport's client address
    assert long_agent.json()["user_agent"] == "u" * 256
    assert no_agent.json()["user_agent"] is None


async def test_s3_3_09_x_forwarded_for_is_never_read_by_the_app(
    db: AsyncSession, db_connection: AsyncConnection
) -> None:
    me = await signed_in(db)
    spoof = {
        "X-Forwarded-For": "198.51.100.66",
        "X-Real-IP": "198.51.100.67",
        "Forwarded": "for=198.51.100.68",
    }
    async with api_client(db_connection, router) as http:
        response = await http.get(WHOAMI, headers=me.headers | spoof)
    assert response.json()["ip"] == "127.0.0.1"


async def test_s3_3_10_database_down_during_the_lookup_is_a_generic_500(
    caplog: pytest.LogCaptureFixture,
) -> None:
    # Token checks pass before the database is needed: a structurally valid token.
    token, _ = issue_access_token(
        make_settings().jwt, user_id=uuid.uuid4(), session_id=uuid.uuid4(), now=clock.now()
    )
    app = create_app(
        make_settings(database=UNREACHABLE_DB),
        health_checks={"database": check_ok},
        api_routers=[router],
    )
    with caplog.at_level(logging.INFO):
        async with app.router.lifespan_context(app), client_for(app) as http:
            response = await http.get(WHOAMI, headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 500
    assert response.json()["code"] == "server.internal_error"
    logged = "\n".join(JsonFormatter().format(r) for r in caplog.records)
    assert token not in logged
    assert token not in response.text


async def test_s3_3_11_the_lookup_is_a_single_query(
    db: AsyncSession, db_connection: AsyncConnection
) -> None:
    me = await signed_in(db)
    statements: list[str] = []

    def record(*args: object) -> None:
        statements.append(str(args[2]))

    event.listen(db_connection.sync_connection, "before_cursor_execute", record)
    try:
        async with api_client(db_connection, router) as http:
            response = await http.get(WHOAMI, headers=me.headers)
    finally:
        event.remove(db_connection.sync_connection, "before_cursor_execute", record)
    assert response.status_code == 200
    queries = [
        s
        for s in statements
        if not s.lstrip().upper().startswith(("SAVEPOINT", "RELEASE", "ROLLBACK"))
    ]
    assert len(queries) == 1


async def test_s3_3_12_tokens_never_reach_the_logs(
    db: AsyncSession, db_connection: AsyncConnection, caplog: pytest.LogCaptureFixture
) -> None:
    me = await signed_in(db)
    with caplog.at_level(logging.DEBUG):
        async with api_client(db_connection, router) as http:
            await http.get(WHOAMI, headers=me.headers)
            await http.get(WHOAMI, headers={"Authorization": "Bearer " + me.access_token + "x"})
    logged = "\n".join(JsonFormatter().format(r) for r in caplog.records)
    assert '"message": "request"' in logged  # the access log line was written
    assert me.access_token not in logged
    assert me.access_token[:40] not in logged
    assert json.dumps(me.user.email) not in logged
