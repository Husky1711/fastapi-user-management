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
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, AsyncSession

from app.core import security
from app.main import create_app
from app.models import AuditLog, User, UserSession
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
    async with asyncio.timeout(WAIT_LIMIT_SECONDS):
        await gate.reached.wait()
        yield task
        gate.release.set()
        await task


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


# --- refresh against revocation (real pool: the requests need their own connections) ---


async def _wait_until_blocked_on_a_lock(engine: AsyncEngine) -> None:
    """Return once another connection of this database waits on a row lock."""
    query = text(
        "SELECT count(*) FROM pg_stat_activity"
        " WHERE datname = current_database() AND wait_event_type = 'Lock'"
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


@pytest.mark.parametrize("revocation", ["logout_all", "password_change"])
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
        refreshing = http.post(REFRESH, json={"refresh_token": stolen["refresh_token"]})
        async with paused_request(gate, refreshing) as rotated:
            if revocation == "logout_all":
                revoke = http.post(LOGOUT_ALL, headers=_bearer(owner))
            else:
                change = _change(PASSWORD, OWNER_PASSWORD)
                revoke = http.post(PASSWORD_ROUTE, json=change, headers=_bearer(owner))
            revoking = asyncio.ensure_future(revoke)
            await _wait_until_blocked_on_a_lock(db_engine)  # it queues behind the rotation
        assert (await revoking).status_code == 204
        successor = rotated.result().json()  # the rotation itself finished first
        reuse = await http.post(REFRESH, json={"refresh_token": successor["refresh_token"]})
        access = await http.get("/api/v1/me", headers=_bearer(successor))
        async with AsyncSession(db_engine) as session:
            survivors = await _active_families(session, email)
        owner_family = await _family_of(http, owner) if revocation == "password_change" else None
    assert (reuse.status_code, access.status_code) == (401, 401)
    assert survivors == ({owner_family} if owner_family else set())


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


async def test_s3_8_03_a_locked_account_refuses_password_change_even_with_the_right_password(
    db: AsyncSession, db_connection: AsyncConnection
) -> None:
    async with api_client(db_connection) as http:
        email, (stolen, owner) = await _account(http, devices=2)
        for guess in range(5):  # the default lockout threshold
            wrong = _change(f"Wrong-Guess-Number-{guess}", ATTACKER_PASSWORD)
            await http.post(PASSWORD_ROUTE, json=wrong, headers=_bearer(stolen))
        right = _change(PASSWORD, ATTACKER_PASSWORD)
        response = await http.post(PASSWORD_ROUTE, json=right, headers=_bearer(stolen))
        owner_still_in = await http.get("/api/v1/me", headers=_bearer(owner))
    assert (response.status_code, response.json()["code"]) == (401, "auth.invalid_credentials")
    assert owner_still_in.status_code == 200
    db.expunge_all()
    user = (await db.execute(select(User).where(User.email == email))).scalar_one()
    assert await security.verify_password(user.password_hash, PASSWORD)
    assert user.failed_login_count == 5  # guesses during the lock were refused, not counted


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
                fixed = await http.post(LOGOUT_ALL, headers=_bearer(owner))
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


async def test_s3_8_05_a_password_change_resets_the_failure_count(
    db: AsyncSession, db_connection: AsyncConnection
) -> None:
    async with api_client(db_connection) as http:
        email, (tokens,) = await _account(http, devices=1)
        wrong = _change("Wrong-Guess-Number-1", OWNER_PASSWORD)
        await http.post(PASSWORD_ROUTE, json=wrong, headers=_bearer(tokens))
        right = _change(PASSWORD, OWNER_PASSWORD)
        assert (
            await http.post(PASSWORD_ROUTE, json=right, headers=_bearer(tokens))
        ).status_code == 204
    db.expunge_all()
    user = (await db.execute(select(User).where(User.email == email))).scalar_one()
    assert user.failed_login_count == 0
