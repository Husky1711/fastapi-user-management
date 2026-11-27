"""Section 3.8: credential and session changes that race each other (security audit fixes).

Each test pauses one request at a chosen point with a `Gate`, runs the competing request,
then lets the first one finish. No sleeps decide the order: where the second request must
be blocked by the database, the test waits until PostgreSQL reports it waiting on a lock.
"""

import asyncio
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Any

import pytest
from argon2 import PasswordHasher
from fastapi import FastAPI
from httpx import AsyncClient, Response
from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, AsyncSession

from app.core import security
from app.core.config import AuthSettings, SessionStrategy
from app.main import create_app
from app.models import AuditLog, User, UserSession, UserStatus
from app.services import auth
from tests.api import api_client
from tests.db import SERVICES, committed_user, service_database_settings
from tests.helpers import check_ok, client_for, make_settings

pytestmark = SERVICES
SIGNUP, LOGIN, REFRESH = "/api/v1/auth/signup", "/api/v1/auth/login", "/api/v1/auth/refresh"
LOGOUT_ALL, PASSWORD_ROUTE = "/api/v1/auth/logout-all", "/api/v1/me/password"
PASSWORD = "Correct-Horse-Battery-9"
OWNER_PASSWORD = "Owners-Fresh-Passphrase-7"
ATTACKER_PASSWORD = "Attackers-Own-Passphrase-3"
WAIT_LIMIT_SECONDS = 10  # only a hang guard: every wait below ends on an event


class Gate:
    """Pauses the first call of a wrapped coroutine function until released."""

    def __init__(self) -> None:
        self.reached = asyncio.Event()
        self.release = asyncio.Event()
        self._used = False

    def wrap[**P, R](
        self, function: Callable[P, Awaitable[R]], *, after: bool
    ) -> Callable[P, Awaitable[R]]:
        async def paused(*args: P.args, **kwargs: P.kwargs) -> R:
            if not after:
                await self._pause()
            result = await function(*args, **kwargs)
            if after:
                await self._pause()
            return result

        return paused

    async def _pause(self) -> None:
        if self._used:
            return
        self._used = True
        self.reached.set()
        await self.release.wait()


@asynccontextmanager
async def paused_request(gate: Gate, request: Awaitable[Response]) -> AsyncIterator[Any]:
    """Start `request`, wait until it reaches the gate, run the block, then let it finish.
    The finished task is yielded; read its result after the block."""
    task: asyncio.Task[Response] = asyncio.ensure_future(request)
    try:
        async with asyncio.timeout(WAIT_LIMIT_SECONDS):
            await gate.reached.wait()
            yield task
    finally:  # always let the paused request finish, or it holds its locks past the test
        gate.release.set()
        async with asyncio.timeout(WAIT_LIMIT_SECONDS):
            await asyncio.gather(task, return_exceptions=True)
    task.result()  # re-raise what the paused request raised, if anything


def _bearer(tokens: dict[str, Any]) -> dict[str, str]:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


async def _login(http: AsyncClient, email: str, password: str = PASSWORD) -> Response:
    return await http.post(LOGIN, json={"email": email, "password": password})


async def _account(http: AsyncClient, devices: int) -> tuple[str, list[dict[str, Any]]]:
    email = f"race-{uuid.uuid4().hex[:12]}@example.com"
    assert (await http.post(SIGNUP, json={"email": email, "password": PASSWORD})).status_code == 202
    logins = [(await _login(http, email)).json() for _ in range(devices)]
    return email, logins


def _change(current: str, new: str) -> dict[str, str]:
    return {"current_password": current, "new_password": new}


async def _active_families(session: AsyncSession, email: str) -> set[uuid.UUID]:
    session.expunge_all()
    rows = await session.execute(
        select(UserSession.family_id)
        .join(User, User.id == UserSession.user_id)
        .where(User.email == email, UserSession.revoked_at.is_(None))
    )
    return set(rows.scalars())


async def _family_of(http: AsyncClient, tokens: dict[str, Any]) -> uuid.UUID:
    page = (await http.get("/api/v1/me/sessions", headers=_bearer(tokens))).json()
    return uuid.UUID(next(item["id"] for item in page["items"] if item["current"]))


async def _actions(db: AsyncSession, user_id: uuid.UUID) -> dict[str, int]:
    """How often each audit action was recorded for the user, ignoring sign-up and logins."""
    rows = await db.execute(select(AuditLog.action).where(AuditLog.actor_user_id == user_id))
    counts: dict[str, int] = {}
    for action in rows.scalars():
        if action not in {"auth.signed_up", "auth.logged_in"}:
            counts[action] = counts.get(action, 0) + 1
    return counts


async def _user(db: AsyncSession, email: str) -> User:
    db.expunge_all()  # read what the requests committed, not a cached object
    return (await db.execute(select(User).where(User.email == email))).scalar_one()


# --- refresh against revocation (real pool: the requests need their own connections) ---


async def _wait_until_queued_on_the_user_lock(engine: AsyncEngine) -> None:
    """Return once a connection waits on a lock held by a transaction that has locked
    the users table (the per-user lock), not on any lock. Matched by the locks themselves,
    not by statement text (PostgreSQL may truncate it)."""
    query = text(
        "SELECT count(*) FROM pg_stat_activity w"
        " WHERE w.datname = current_database() AND w.wait_event_type = 'Lock'"
        " AND EXISTS (SELECT 1 FROM pg_locks l WHERE l.granted"
        " AND l.relation = 'users'::regclass AND l.pid = ANY(pg_blocking_pids(w.pid)))"
    )
    async with asyncio.timeout(WAIT_LIMIT_SECONDS), engine.connect() as connection:
        # PostgreSQL can't signal us, so this polls its state; the order is still decided
        # by the lock, not by the delay.
        while (await connection.execute(query)).scalar_one() == 0:  # noqa: ASYNC110
            await asyncio.sleep(0.01)


@pytest.fixture
async def pooled_app() -> AsyncIterator[FastAPI]:
    settings = make_settings(database=service_database_settings(pool_size=5, max_overflow=5))
    app = create_app(settings, health_checks={"database": check_ok})
    async with app.router.lifespan_context(app):
        yield app


REVOCATIONS = ["logout_all", "password_change", "end_that_session", "revoke_others"]


def _revoke(
    http: AsyncClient, owner: dict[str, Any], revocation: str, stolen_family: uuid.UUID
) -> Awaitable[Response]:
    reauth = {"current_password": PASSWORD}
    if revocation == "logout_all":
        return http.post(LOGOUT_ALL, json=reauth, headers=_bearer(owner))
    if revocation == "password_change":
        change = _change(PASSWORD, OWNER_PASSWORD)
        return http.post(PASSWORD_ROUTE, json=change, headers=_bearer(owner))
    if revocation == "end_that_session":
        path = f"/api/v1/me/sessions/{stolen_family}/revoke"
        return http.post(path, json=reauth, headers=_bearer(owner))
    return http.post("/api/v1/me/sessions/revoke-others", json=reauth, headers=_bearer(owner))


@pytest.mark.parametrize("revocation", REVOCATIONS)
async def test_s3_8_01_a_refresh_in_flight_cannot_outlive_a_revocation(
    db_engine: AsyncEngine,
    pooled_app: FastAPI,
    monkeypatch: pytest.MonkeyPatch,
    revocation: str,
) -> None:
    gate = Gate()
    monkeypatch.setattr(auth, "_rotate", gate.wrap(auth._rotate, after=False))
    password_hash = await security.hash_password(PASSWORD)
    async with committed_user(db_engine, password_hash) as email, client_for(pooled_app) as http:
        stolen, owner = (await _login(http, email)).json(), (await _login(http, email)).json()
        stolen_family, owner_family = await _family_of(http, stolen), await _family_of(http, owner)
        refreshing = http.post(REFRESH, json={"refresh_token": stolen["refresh_token"]})
        async with paused_request(gate, refreshing) as rotated:
            revoking = asyncio.ensure_future(_revoke(http, owner, revocation, stolen_family))
            await _wait_until_queued_on_the_user_lock(db_engine)  # behind the rotation
        assert (await revoking).status_code == 204
        successor = rotated.result().json()  # the rotation itself finished first
        reuse = await http.post(REFRESH, json={"refresh_token": successor["refresh_token"]})
        access = await http.get("/api/v1/me", headers=_bearer(successor))
        async with AsyncSession(db_engine) as session:
            survivors = await _active_families(session, email)
    assert (reuse.status_code, access.status_code) == (401, 401)
    assert survivors == (set() if revocation == "logout_all" else {owner_family})


# --- login against password change (one test connection: the requests take turns) ---


@pytest.mark.parametrize("rehash_due", [False, True])
async def test_s3_8_02_a_login_checked_against_the_old_password_is_refused(
    db: AsyncSession,
    db_connection: AsyncConnection,
    monkeypatch: pytest.MonkeyPatch,
    rehash_due: bool,
) -> None:
    async with api_client(db_connection) as http:
        email, (owner,) = await _account(http, devices=1)
        if rehash_due:  # an older, weaker hash: a successful login would replace it
            weak = PasswordHasher(time_cost=1, memory_cost=8, parallelism=1).hash(PASSWORD)
            user = (await db.execute(select(User).where(User.email == email))).scalar_one()
            user.password_hash = weak
            await db.flush()
        gate = Gate()
        verify = gate.wrap(security.verify_password, after=True)
        monkeypatch.setattr("app.services.auth.verify_password", verify)
        async with paused_request(gate, _login(http, email)) as attacker:
            change = _change(PASSWORD, OWNER_PASSWORD)
            changed = await http.post(PASSWORD_ROUTE, json=change, headers=_bearer(owner))
        old = await _login(http, email)
        new = await _login(http, email, OWNER_PASSWORD)
    assert changed.status_code == 204
    assert (attacker.result().status_code, old.status_code, new.status_code) == (401, 401, 200)
    refused = await db.execute(select(AuditLog).where(AuditLog.action == "auth.login_refused"))
    assert len(refused.scalars().all()) == 1


# --- password change: lockout and stale checks ---


async def test_s3_8_03_a_stolen_token_gets_three_guesses_then_its_session_ends(
    db: AsyncSession, db_connection: AsyncConnection
) -> None:
    """ADR-0012: wrong re-entered passwords use up the *session's* budget (3), which ends
    that session; the owner's account is not locked and their device keeps working."""
    async with api_client(db_connection) as http:
        email, (stolen, owner) = await _account(http, devices=2)
        guesses = []
        for guess in range(3):
            wrong = _change(f"Wrong-Guess-Number-{guess}", ATTACKER_PASSWORD)
            guesses.append(await http.post(PASSWORD_ROUTE, json=wrong, headers=_bearer(stolen)))
        right = _change(PASSWORD, ATTACKER_PASSWORD)
        too_late = await http.post(PASSWORD_ROUTE, json=right, headers=_bearer(stolen))
        refresh = await http.post(REFRESH, json={"refresh_token": stolen["refresh_token"]})
        owner_still_in = await http.get("/api/v1/me", headers=_bearer(owner))
        owner_login = await _login(http, email)
    assert [g.json()["code"] for g in guesses] == ["auth.invalid_credentials"] * 3
    assert (too_late.status_code, too_late.json()["code"]) == (401, "auth.invalid_token")
    assert refresh.status_code == 401  # the thief's refresh token died with the session
    assert (owner_still_in.status_code, owner_login.status_code) == (200, 200)
    user = await _user(db, email)
    assert await security.verify_password(user.password_hash, PASSWORD)
    assert (user.failed_login_count, user.locked_until) == (0, None)
    actions = await _actions(db, user.id)
    assert actions["auth.password_change_failed"] == 3
    assert actions["auth.session_ended_after_reauth_failures"] == 1


@pytest.mark.parametrize("remedy", ["password_change", "logout_all"])
async def test_s3_8_04_a_stale_password_change_cannot_undo_the_owners_remedy(
    db: AsyncSession, db_connection: AsyncConnection, monkeypatch: pytest.MonkeyPatch, remedy: str
) -> None:
    async with api_client(db_connection) as http:
        email, (stolen, owner) = await _account(http, devices=2)
        gate = Gate()
        hashing = gate.wrap(security.hash_password, after=True)
        monkeypatch.setattr("app.services.me.hash_password", hashing)
        attack = _change(PASSWORD, ATTACKER_PASSWORD)
        attacking = http.post(PASSWORD_ROUTE, json=attack, headers=_bearer(stolen))
        async with paused_request(gate, attacking) as attacker:
            if remedy == "password_change":
                change = _change(PASSWORD, OWNER_PASSWORD)
                fixed = await http.post(PASSWORD_ROUTE, json=change, headers=_bearer(owner))
            else:
                reauth = {"current_password": PASSWORD}
                fixed = await http.post(LOGOUT_ALL, json=reauth, headers=_bearer(owner))
        owner_password = OWNER_PASSWORD if remedy == "password_change" else PASSWORD
        owner_login = await _login(http, email, owner_password)
        attacker_login = await _login(http, email, ATTACKER_PASSWORD)
    assert fixed.status_code == 204
    assert (attacker.result().status_code, attacker.result().json()["code"]) == (
        401,
        "auth.invalid_credentials" if remedy == "password_change" else "auth.invalid_token",
    )
    assert (owner_login.status_code, attacker_login.status_code) == (200, 401)
    refused = await db.execute(
        select(AuditLog).where(AuditLog.action == "auth.password_change_refused")
    )
    assert len(refused.scalars().all()) == 1


async def test_s3_8_05_a_successful_reentry_restores_the_sessions_budget(
    db: AsyncSession, db_connection: AsyncConnection
) -> None:
    """Two typos, then the right password: the budget is back to 3 (review round 5, L1)."""
    async with api_client(db_connection) as http:
        email, (tokens, _other) = await _account(http, devices=2)
        reauth = "/api/v1/me/sessions/revoke-others"
        for typo in ("Typo-Number-0001", "Typo-Number-0002"):
            await http.post(reauth, json={"current_password": typo}, headers=_bearer(tokens))
        ok = await http.post(reauth, json={"current_password": PASSWORD}, headers=_bearer(tokens))
        for typo in ("Typo-Number-0003", "Typo-Number-0004"):
            await http.post(reauth, json={"current_password": typo}, headers=_bearer(tokens))
        still_in = await http.get("/api/v1/me", headers=_bearer(tokens))
    assert (ok.status_code, still_in.status_code) == (204, 200)
    db.expunge_all()
    rows = await db.execute(
        select(UserSession.reauth_attempts)
        .join(User, User.id == UserSession.user_id)
        .where(User.email == email, UserSession.revoked_at.is_(None))
    )
    assert list(rows.scalars()) == [2]


async def _pause_password_change_after_hashing(
    http: AsyncClient, monkeypatch: pytest.MonkeyPatch, tokens: dict[str, Any]
) -> tuple[Gate, Awaitable[Response]]:
    gate = Gate()
    hashing = gate.wrap(security.hash_password, after=True)
    monkeypatch.setattr("app.services.me.hash_password", hashing)
    change = _change(PASSWORD, ATTACKER_PASSWORD)
    return gate, http.post(PASSWORD_ROUTE, json=change, headers=_bearer(tokens))


@pytest.mark.parametrize("route", ["password", "logout_all"])
async def test_s3_8_06_a_burst_of_parallel_guesses_gets_three_verifications(
    db_engine: AsyncEngine, pooled_app: FastAPI, monkeypatch: pytest.MonkeyPatch, route: str
) -> None:
    """Review round 5, H1: the budget is reserved under the user lock before Argon2 runs,
    so twelve parallel guesses (the right one included) get at most three verifications,
    and the session ends."""
    verified: list[str] = []
    real_verify = security.verify_password

    async def counting_verify(stored_hash: str, password: str) -> bool:
        verified.append(password)
        return await real_verify(stored_hash, password)

    monkeypatch.setattr("app.services.auth.verify_password", counting_verify)
    password_hash = await security.hash_password(PASSWORD)
    async with committed_user(db_engine, password_hash) as email, client_for(pooled_app) as http:
        stolen = (await _login(http, email)).json()
        guesses = [f"Wrong-Guess-Number-{n:02d}" for n in range(11)] + [PASSWORD]
        verified.clear()  # the login above verified once

        def attempt(guess: str) -> Awaitable[Response]:
            if route == "password":
                body = _change(guess, ATTACKER_PASSWORD)
                return http.post(PASSWORD_ROUTE, json=body, headers=_bearer(stolen))
            body = {"current_password": guess}
            return http.post(LOGOUT_ALL, json=body, headers=_bearer(stolen))

        answers = await asyncio.gather(*(attempt(guess) for guess in guesses))
        after = await http.get("/api/v1/me", headers=_bearer(stolen))
        async with AsyncSession(db_engine) as session:
            user = (await session.execute(select(User).where(User.email == email))).scalar_one()
            still_password = await security.verify_password(user.password_hash, PASSWORD)
    assert len(verified) <= 3
    assert [a.status_code for a in answers].count(401) >= len(guesses) - 1
    assert after.status_code == 401 or PASSWORD in verified  # ended, or the right guess won
    if PASSWORD not in verified:  # the usual case: the right guess was never even checked
        assert all(a.status_code == 401 for a in answers)
        assert still_password


async def test_s3_8_07_an_account_disabled_while_the_change_is_hashing_refuses_it(
    db: AsyncSession, db_connection: AsyncConnection, monkeypatch: pytest.MonkeyPatch
) -> None:
    async with api_client(db_connection) as http:
        email, (stolen,) = await _account(http, devices=1)
        gate, changing = await _pause_password_change_after_hashing(http, monkeypatch, stolen)
        async with paused_request(gate, changing) as change:
            user = await _user(db, email)
            user.status = UserStatus.DISABLED
            await db.flush()
    assert (change.result().status_code, change.result().json()["code"]) == (
        401,
        "auth.invalid_credentials",
    )
    user = await _user(db, email)
    assert await security.verify_password(user.password_hash, PASSWORD)


@pytest.mark.parametrize(
    ("strategy", "kept"),
    [(SessionStrategy.REPLACE_ALL, 1), (SessionStrategy.LIMIT_SESSIONS, 2)],
)
async def test_s3_8_08_concurrent_logins_respect_the_session_strategy(
    db_engine: AsyncEngine, strategy: SessionStrategy, kept: int
) -> None:
    settings = make_settings(
        database=service_database_settings(pool_size=5, max_overflow=5),
        auth=AuthSettings(session_strategy=strategy, max_sessions=2),
    )
    app = create_app(settings, health_checks={"database": check_ok})
    password_hash = await security.hash_password(PASSWORD)
    async with (
        committed_user(db_engine, password_hash) as email,
        app.router.lifespan_context(app),
        client_for(app) as http,
    ):
        logins = await asyncio.gather(*(_login(http, email) for _ in range(6)))
        async with AsyncSession(db_engine) as session:
            survivors = await _active_families(session, email)
    assert [response.status_code for response in logins] == [200] * 6
    assert len(survivors) == kept  # the per-user lock serializes the count-then-insert


@pytest.mark.parametrize("password", [PASSWORD, "Wrong-Guess-Number-1"])
async def test_s3_8_09_a_user_removed_mid_login_gets_401_not_500(
    db: AsyncSession,
    db_connection: AsyncConnection,
    monkeypatch: pytest.MonkeyPatch,
    password: str,
) -> None:
    async with api_client(db_connection) as http:
        email, _ = await _account(http, devices=0)
        gate = Gate()
        verify = gate.wrap(security.verify_password, after=True)
        monkeypatch.setattr("app.services.auth.verify_password", verify)
        async with paused_request(gate, _login(http, email, password)) as login:
            await db.execute(delete(User).where(User.email == email))
            await db.flush()
    assert (login.result().status_code, login.result().json()["code"]) == (
        401,
        "auth.invalid_credentials",
    )
    refused = await db.execute(select(AuditLog).where(AuditLog.action == "auth.login_refused"))
    rows = refused.scalars().all()
    if password == PASSWORD:  # reached the locked re-check: refused, audited with no actor
        assert [row.actor_user_id for row in rows] == [None]
    else:  # wrong password: nothing left to count, nothing audited
        assert rows == []


@pytest.mark.parametrize(
    "policy",
    [
        AuthSettings(session_strategy=SessionStrategy.REPLACE_ALL),
        AuthSettings(session_strategy=SessionStrategy.LIMIT_SESSIONS, max_sessions=1),
    ],
    ids=["replace_all", "limit_sessions"],
)
async def test_s3_8_12_a_login_that_ends_other_sessions_also_ends_a_refresh_in_flight(
    db_engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch, policy: AuthSettings
) -> None:
    settings = make_settings(
        database=service_database_settings(pool_size=5, max_overflow=5), auth=policy
    )
    app = create_app(settings, health_checks={"database": check_ok})
    gate = Gate()
    monkeypatch.setattr(auth, "_rotate", gate.wrap(auth._rotate, after=False))
    password_hash = await security.hash_password(PASSWORD)
    async with (
        committed_user(db_engine, password_hash) as email,
        app.router.lifespan_context(app),
        client_for(app) as http,
    ):
        old = (await _login(http, email)).json()
        refreshing = http.post(REFRESH, json={"refresh_token": old["refresh_token"]})
        async with paused_request(gate, refreshing) as rotated:
            logging_in = asyncio.ensure_future(_login(http, email))
            await _wait_until_queued_on_the_user_lock(db_engine)  # behind the rotation
        newest = (await logging_in).json()
        successor = rotated.result().json()
        dead = await http.post(REFRESH, json={"refresh_token": successor["refresh_token"]})
        async with AsyncSession(db_engine) as session:
            survivors = await _active_families(session, email)
        newest_family = await _family_of(http, newest)
    assert dead.status_code == 401  # the strategy saw the successor and ended it
    assert survivors == {newest_family}


@pytest.mark.parametrize("route", ["logout_all", "revoke_others", "end_other_device"])
async def test_s3_8_13_a_stale_reentry_cannot_end_sessions_after_a_password_change(
    db: AsyncSession, db_connection: AsyncConnection, monkeypatch: pytest.MonkeyPatch, route: str
) -> None:
    """Review round 5, H1: the session-ending routes re-check under the user lock what may
    have changed while Argon2 ran. The attacker's re-entry verified the old password; the
    owner changes it (ending the attacker's session) before the attacker's write."""
    async with api_client(db_connection) as http:
        email, (stolen, owner) = await _account(http, devices=2)
        owner_family = await _family_of(http, owner)
        gate = Gate()
        verify = gate.wrap(security.verify_password, after=True)
        monkeypatch.setattr("app.services.auth.verify_password", verify)
        reauth = {"current_password": PASSWORD}
        path = {
            "logout_all": LOGOUT_ALL,
            "revoke_others": "/api/v1/me/sessions/revoke-others",
            "end_other_device": f"/api/v1/me/sessions/{owner_family}/revoke",
        }[route]
        attacking = http.post(path, json=reauth, headers=_bearer(stolen))
        async with paused_request(gate, attacking) as attacker:
            change = _change(PASSWORD, OWNER_PASSWORD)
            changed = await http.post(PASSWORD_ROUTE, json=change, headers=_bearer(owner))
        owner_after = await http.get("/api/v1/me", headers=_bearer(owner))
    assert changed.status_code == 204
    assert attacker.result().status_code == 401
    assert owner_after.status_code == 200  # the stale request ended nothing
    user = await _user(db, email)
    assert (await _actions(db, user.id))["auth.reauth_refused"] == 1


@pytest.mark.parametrize("change", ["disabled_before_reserving", "removed_while_verifying"])
async def test_s3_8_14_reentry_on_an_account_that_changes_underneath_is_refused(
    db: AsyncSession, db_connection: AsyncConnection, monkeypatch: pytest.MonkeyPatch, change: str
) -> None:
    """The reservation re-reads the account under the lock (disabled meanwhile: refused and
    audited); a user removed while Argon2 runs gets a plain 401, never a 500."""
    async with api_client(db_connection) as http:
        email, (tokens,) = await _account(http, devices=1)
        gate = Gate()
        if change == "disabled_before_reserving":
            # Paused before the reservation's transaction opens (the test shares its connection).
            monkeypatch.setattr(
                auth, "_reserve_reauth", gate.wrap(auth._reserve_reauth, after=False)
            )
            body = {"current_password": PASSWORD}
        else:
            verify = gate.wrap(security.verify_password, after=True)
            monkeypatch.setattr("app.services.auth.verify_password", verify)
            body = {"current_password": "Wrong-Guess-Number-1"}
        request = http.post(LOGOUT_ALL, json=body, headers=_bearer(tokens))
        async with paused_request(gate, request) as attempt:
            if change == "disabled_before_reserving":
                user = await _user(db, email)
                user.status = UserStatus.DISABLED
                await db.flush()
            else:
                await db.execute(delete(User).where(User.email == email))
                await db.flush()
    assert (attempt.result().status_code, attempt.result().json()["code"]) == (
        401,
        "auth.invalid_credentials",
    )
    refused = await db.execute(select(AuditLog).where(AuditLog.action == "auth.reauth_refused"))
    assert len(refused.scalars().all()) == (1 if change == "disabled_before_reserving" else 0)
