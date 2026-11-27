"""Section 3.4: sign-up and login through the real routes, on the real PostgreSQL."""

import asyncio
import logging
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest
from argon2 import PasswordHasher
from httpx import AsyncClient, Response
from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, AsyncSession

from app.core import clock, security
from app.core.client import ClientInfo
from app.core.config import AuthSettings, SessionStrategy
from app.core.logging import JsonFormatter
from app.infra.database import is_unique_violation
from app.main import create_app
from app.models import AuditLog, RevokeReason, User, UserSession, UserStatus
from app.services import auth
from tests.api import api_client
from tests.db import SERVICES, UNREACHABLE_DB, service_database_settings
from tests.helpers import check_ok, client_for, make_settings

pytestmark = SERVICES
SIGNUP, LOGIN = "/api/v1/auth/signup", "/api/v1/auth/login"
PASSWORD = "Correct-Horse-Battery-9"


def _email() -> str:
    return f"user-{uuid.uuid4().hex[:12]}@example.com"


async def _user(db: AsyncSession, email: str) -> User | None:
    return (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()


async def _registered(http: AsyncClient, email: str, password: str = PASSWORD) -> None:
    response = await http.post(SIGNUP, json={"email": email, "password": password})
    assert response.status_code == 202


async def _login(
    http: AsyncClient, email: str, password: str = PASSWORD, agent: str = "pytest"
) -> Response:
    body = {"email": email, "password": password}
    return await http.post(LOGIN, json=body, headers={"User-Agent": agent})


async def _must_user(db: AsyncSession, email: str) -> User:
    db.expunge_all()  # read what the API committed, not a cached object
    user = await _user(db, email)
    assert user is not None
    return user


async def _families(db: AsyncSession, user_id: uuid.UUID) -> dict[uuid.UUID, RevokeReason | None]:
    rows = await db.execute(
        select(UserSession.family_id, UserSession.revoked_reason).where(
            UserSession.user_id == user_id
        )
    )
    return {row.family_id: row.revoked_reason for row in rows}


async def _actions(db: AsyncSession, user_id: uuid.UUID) -> list[str]:
    rows = await db.execute(
        select(AuditLog.action).where(AuditLog.actor_user_id == user_id).order_by(AuditLog.id)
    )
    return list(rows.scalars())


async def test_s3_4_01_signup_creates_an_unverified_ordinary_user(
    db: AsyncSession, db_connection: AsyncConnection
) -> None:
    email = _email()
    async with api_client(db_connection) as http:
        response = await http.post(
            SIGNUP, json={"email": email, "password": PASSWORD, "full_name": "Ada"}
        )
    assert response.status_code == 202
    assert set(response.json()) == {"detail"}
    user = await _user(db, email)
    assert user is not None
    assert (user.email_verified, user.is_platform_admin, user.full_name) == (False, False, "Ada")
    assert user.password_hash.startswith("$argon2id$")
    assert await _actions(db, user.id) == ["auth.signed_up"]


async def test_s3_4_02_signup_with_a_taken_email_looks_the_same_and_changes_nothing(
    db: AsyncSession, db_connection: AsyncConnection
) -> None:
    email = _email()
    async with api_client(db_connection) as http:
        first = await http.post(SIGNUP, json={"email": email, "password": PASSWORD})
        before = await _user(db, email)
        assert before is not None
        old_hash = before.password_hash
        again = await http.post(
            SIGNUP,
            json={"email": email.upper(), "password": "Another-Passw0rd-xyz", "full_name": "Eve"},
        )
    assert (first.status_code, again.status_code) == (202, 202)
    assert first.json() == again.json()
    db.expunge_all()
    after = await _user(db, email)
    assert after is not None
    assert (after.password_hash, after.full_name) == (old_hash, None)


@pytest.mark.parametrize(
    ("body", "status", "code"),
    [
        ({"email": "new@example.com", "password": "short"}, 422, "user.password_weak"),
        ({"email": "not-an-email", "password": PASSWORD}, 422, "user.email_invalid"),
        (
            {"email": "new@example.com", "password": PASSWORD, "is_platform_admin": True},
            422,
            "request.validation_failed",
        ),
        ({"email": "new@example.com"}, 422, "request.validation_failed"),
        ({"email": "new@example.com", "password": "x" * 2000}, 422, "request.validation_failed"),
    ],
)
async def test_s3_4_03_invalid_signups_create_nothing(
    db: AsyncSession,
    db_connection: AsyncConnection,
    body: dict[str, object],
    status: int,
    code: str,
) -> None:
    async with api_client(db_connection) as http:
        response = await http.post(SIGNUP, json=body)
    assert (response.status_code, response.json()["code"]) == (status, code)
    assert await _user(db, "new@example.com") is None


async def test_s3_4_04_signup_can_be_switched_off(db_connection: AsyncConnection) -> None:
    async with api_client(db_connection, auth=AuthSettings(signup_enabled=False)) as http:
        response = await http.post(SIGNUP, json={"email": _email(), "password": PASSWORD})
    assert response.status_code == 404


async def test_s3_4_05_login_issues_tokens_and_records_the_login(
    db: AsyncSession, db_connection: AsyncConnection, monkeypatch: pytest.MonkeyPatch
) -> None:
    email = _email()
    async with api_client(db_connection) as http:
        await _registered(http, email)
        await db.execute(update(User).where(User.email == email).values(failed_login_count=2))
        frozen = clock.now()
        monkeypatch.setattr(clock, "now", lambda: frozen)
        response = await _login(http, email.upper())
        assert response.status_code == 200
        body = response.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == 900
    assert body["refresh_expires_in"] == 14 * 24 * 3600
    user = await _must_user(db, email)
    assert (user.failed_login_count, user.locked_until, user.last_login_at) == (0, None, frozen)
    families = await _families(db, user.id)
    assert list(families.values()) == [None]
    assert await _actions(db, user.id) == ["auth.signed_up", "auth.logged_in"]


@pytest.mark.parametrize(
    "case", ["wrong_password", "unknown_email", "disabled", "deleted", "not_an_email"]
)
async def test_s3_4_06_every_refusal_is_the_same_401(
    db: AsyncSession, db_connection: AsyncConnection, case: str
) -> None:
    email = _email()
    async with api_client(db_connection) as http:
        await _registered(http, email)
        if case == "disabled":
            await db.execute(
                update(User).where(User.email == email).values(status=UserStatus.DISABLED)
            )
        if case == "deleted":
            await db.execute(
                update(User)
                .where(User.email == email)
                .values(status=UserStatus.DELETED, deleted_at=clock.now())
            )
        login_as = {"unknown_email": _email(), "not_an_email": "nobody"}.get(case, email)
        password = "Wrong-Password-123" if case == "wrong_password" else PASSWORD
        response = await http.post(LOGIN, json={"email": login_as, "password": password})
    assert response.status_code == 401
    assert response.json()["code"] == "auth.invalid_credentials"
    assert response.json()["detail"] == "The email or password is incorrect."


async def test_s3_4_07_unknown_email_and_wrong_password_both_run_one_argon2_verify(
    db_connection: AsyncConnection, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[str] = []
    real_verify = security._verify

    def spy(password_hash: str, password: str) -> bool:
        calls.append(password_hash[:10])
        return real_verify(password_hash, password)

    email = _email()
    async with api_client(db_connection) as http:
        await _registered(http, email)
        monkeypatch.setattr(security, "_verify", spy)
        await http.post(LOGIN, json={"email": _email(), "password": PASSWORD})
        unknown_calls = len(calls)
        await http.post(LOGIN, json={"email": email, "password": "Wrong-Password-123"})
    assert unknown_calls == 1
    assert len(calls) == 2
    assert all(c.startswith("$argon2id") for c in calls)


async def test_s3_4_08_five_failures_lock_the_account_even_for_the_right_password(
    db: AsyncSession, db_connection: AsyncConnection
) -> None:
    email = _email()
    async with api_client(db_connection) as http:
        await _registered(http, email)
        for _ in range(5):
            assert (
                await http.post(LOGIN, json={"email": email, "password": "Wrong-Password-123"})
            ).status_code == 401
        locked = await _login(http, email)
    assert locked.status_code == 401
    assert locked.json()["code"] == "auth.invalid_credentials"
    user = await _user(db, email)
    assert user is not None
    assert user.failed_login_count == 5
    assert user.locked_until is not None
    actions = await _actions(db, user.id)
    assert actions.count("auth.login_failed") == 5
    assert actions.count("auth.account_locked") == 1
    assert actions[-1] == "auth.login_refused"
    assert await _families(db, user.id) == {}


async def test_s3_4_09_success_resets_the_count_and_the_lock_ends_on_time(
    db: AsyncSession, db_connection: AsyncConnection, monkeypatch: pytest.MonkeyPatch
) -> None:
    email = _email()
    start = datetime(2031, 3, 4, 5, 6, 7, tzinfo=UTC)
    now = [start]
    monkeypatch.setattr(clock, "now", lambda: now[0])
    wrong = {"email": email, "password": "Wrong-Password-123"}
    async with api_client(db_connection) as http:
        await _registered(http, email)
        for _ in range(4):
            await http.post(LOGIN, json=wrong)
        assert (await _login(http, email)).status_code == 200
        assert (await _must_user(db, email)).failed_login_count == 0
        for _ in range(5):
            await http.post(LOGIN, json=wrong)
        now[0] = start + timedelta(minutes=15) - timedelta(microseconds=1)
        still_locked = await _login(http, email)
        now[0] = start + timedelta(minutes=15)
        unlocked = await _login(http, email)
    assert still_locked.status_code == 401
    assert unlocked.status_code == 200


async def test_s3_4_09_failures_during_a_lock_do_not_extend_it(
    db: AsyncSession, db_connection: AsyncConnection
) -> None:
    email = _email()
    wrong = {"email": email, "password": "Wrong-Password-123"}
    async with api_client(db_connection) as http:
        await _registered(http, email)
        for _ in range(5):
            await http.post(LOGIN, json=wrong)
        locked_until = (await _must_user(db, email)).locked_until
        for _ in range(3):
            await http.post(LOGIN, json=wrong)
    assert (await _must_user(db, email)).locked_until == locked_until


@pytest.fixture
async def committed_user(db_engine: AsyncEngine) -> AsyncIterator[str]:
    """A user committed for real (concurrency needs several connections); removed after."""
    email = _email()
    password_hash = await security.hash_password(PASSWORD)
    async with AsyncSession(db_engine) as session, session.begin():
        session.add(User(id=uuid.uuid4(), email=email, password_hash=password_hash))
    yield email
    async with AsyncSession(db_engine) as session, session.begin():
        user_id = (await session.execute(select(User.id).where(User.email == email))).scalar_one()
        await session.execute(delete(AuditLog).where(AuditLog.actor_user_id == user_id))
        await session.execute(delete(User).where(User.id == user_id))


async def test_s3_4_10_concurrent_failures_are_all_counted(
    db_engine: AsyncEngine, committed_user: str
) -> None:
    settings = make_settings(database=service_database_settings(pool_size=5, max_overflow=5))
    app = create_app(settings, health_checks={"database": check_ok})
    wrong = {"email": committed_user, "password": "Wrong-Password-123"}
    async with app.router.lifespan_context(app), client_for(app) as http:
        responses = await asyncio.gather(*(http.post(LOGIN, json=wrong) for _ in range(10)))
    assert {r.status_code for r in responses} == {401}
    async with AsyncSession(db_engine) as session:
        user = (
            await session.execute(select(User).where(User.email == committed_user))
        ).scalar_one()
        locks = await session.execute(
            select(func.count()).where(
                AuditLog.actor_user_id == user.id, AuditLog.action == "auth.account_locked"
            )
        )
    assert user.failed_login_count == 10
    assert user.locked_until is not None
    assert locks.scalar_one() == 1


async def test_s3_4_11_login_upgrades_an_old_hash(
    db: AsyncSession, db_connection: AsyncConnection
) -> None:
    email = _email()
    old = PasswordHasher(time_cost=2, memory_cost=19456, parallelism=1).hash(PASSWORD)
    async with api_client(db_connection) as http:
        await _registered(http, email)
        await db.execute(update(User).where(User.email == email).values(password_hash=old))
        response = await _login(http, email)
    assert response.status_code == 200
    upgraded = (await _must_user(db, email)).password_hash
    assert upgraded != old
    assert upgraded.startswith("$argon2id$v=19$m=65536,t=3,p=4$")
    assert await security.verify_password(upgraded, PASSWORD)


async def _login_n(
    db: AsyncSession, db_connection: AsyncConnection, strategy: SessionStrategy, agents: list[str]
) -> dict[uuid.UUID, RevokeReason | None]:
    email = _email()
    auth = AuthSettings(session_strategy=strategy, max_sessions=3)
    async with api_client(db_connection, auth=auth) as http:
        await _registered(http, email)
        for agent in agents:
            assert (await _login(http, email, agent=agent)).status_code == 200
    user = await _user(db, email)
    assert user is not None
    return await _families(db, user.id)


async def test_s3_4_12_allow_multiple_keeps_every_session(
    db: AsyncSession, db_connection: AsyncConnection
) -> None:
    families = await _login_n(db, db_connection, SessionStrategy.ALLOW_MULTIPLE, ["a", "b", "a"])
    assert list(families.values()) == [None, None, None]


async def test_s3_4_13_replace_all_keeps_only_the_newest(
    db: AsyncSession, db_connection: AsyncConnection
) -> None:
    families = await _login_n(db, db_connection, SessionStrategy.REPLACE_ALL, ["a", "b", "c"])
    assert sorted(map(str, families.values())) == sorted(["None", "replaced", "replaced"])


async def test_s3_4_14_limit_sessions_ends_the_oldest(
    db: AsyncSession, db_connection: AsyncConnection, monkeypatch: pytest.MonkeyPatch
) -> None:
    start = clock.now()
    tick = [0]

    def advancing() -> datetime:
        tick[0] += 1
        return start + timedelta(seconds=tick[0])

    monkeypatch.setattr(clock, "now", advancing)
    families = await _login_n(
        db, db_connection, SessionStrategy.LIMIT_SESSIONS, ["a", "b", "c", "d"]
    )
    active = [f for f, reason in families.items() if reason is None]
    assert len(active) == 3
    rows = await db.execute(
        select(UserSession.family_id).where(UserSession.revoked_reason == RevokeReason.REPLACED)
    )
    replaced = list(rows.scalars())
    started = await db.execute(
        select(UserSession.family_id)
        .where(UserSession.family_id.in_(families))
        .order_by(UserSession.family_started_at)
        .limit(1)
    )
    assert replaced == [started.scalar_one()]  # the oldest one


async def test_s3_4_15_replace_same_device_ends_only_that_device(
    db: AsyncSession, db_connection: AsyncConnection
) -> None:
    families = await _login_n(
        db, db_connection, SessionStrategy.REPLACE_SAME_DEVICE, ["phone", "laptop", "phone"]
    )
    assert sorted(map(str, families.values())) == sorted(["None", "None", "replaced"])


async def test_s3_4_16_database_down_at_login_is_a_generic_500_without_secrets(
    caplog: pytest.LogCaptureFixture,
) -> None:
    app = create_app(make_settings(database=UNREACHABLE_DB), health_checks={"database": check_ok})
    email = "secret.person@example.com"
    with caplog.at_level(logging.INFO):
        async with app.router.lifespan_context(app), client_for(app) as http:
            response = await http.post(LOGIN, json={"email": email, "password": PASSWORD})
    assert response.status_code == 500
    logged = "\n".join(JsonFormatter().format(r) for r in caplog.records)
    for secret in (PASSWORD, email, "secret.person"):
        assert secret not in logged
        assert secret not in response.text


class _DriverError(Exception):
    """Stands in for asyncpg's error, which carries SQLSTATE and constraint name."""

    def __init__(self, sqlstate: str, constraint_name: str | None) -> None:
        super().__init__(f"{sqlstate} {constraint_name}")
        self.sqlstate, self.constraint_name = sqlstate, constraint_name


def _integrity_error(sqlstate: str, constraint_name: str | None) -> IntegrityError:
    adapted = Exception("adapted")
    adapted.__cause__ = _DriverError(sqlstate, constraint_name)
    return IntegrityError("INSERT", {}, adapted)


def test_s3_4_03_only_the_email_constraint_means_taken() -> None:
    assert is_unique_violation(_integrity_error("23505", "uq_users_email"), "uq_users_email")
    for sqlstate, name in [
        ("23505", "uq_users_email_v2"),  # a longer name that contains it
        ("23503", "uq_users_email"),  # right name, but not a unique violation
        ("23503", "fk_audit_logs_actor_user_id_users"),
        ("23505", None),
    ]:
        assert not is_unique_violation(_integrity_error(sqlstate, name), "uq_users_email")


async def test_s3_4_03_any_other_integrity_error_at_signup_is_raised(
    db_connection: AsyncConnection,
) -> None:
    """A real CHECK violation (bypassing the schema's 200-character cap) is a bug, not
    "email taken": it must surface, never be swallowed as a 202."""
    async with AsyncSession(bind=db_connection, join_transaction_mode="create_savepoint") as db:
        with pytest.raises(IntegrityError):
            await auth.signup(
                db,
                email=_email(),
                password=PASSWORD,
                full_name="N" * 201,
                client=ClientInfo(ip=None, user_agent=None),
            )


@pytest.fixture
async def race_email(db_engine: AsyncEngine) -> AsyncIterator[str]:
    email = _email()
    yield email
    async with AsyncSession(db_engine) as session, session.begin():
        ids = list((await session.execute(select(User.id).where(User.email == email))).scalars())
        await session.execute(delete(AuditLog).where(AuditLog.actor_user_id.in_(ids)))
        await session.execute(delete(User).where(User.id.in_(ids)))


async def test_s3_4_19_concurrent_signups_with_one_email_create_one_user(
    db_engine: AsyncEngine, race_email: str
) -> None:
    settings = make_settings(database=service_database_settings(pool_size=5, max_overflow=5))
    app = create_app(settings, health_checks={"database": check_ok})
    bodies = [
        {"email": race_email, "password": PASSWORD},
        {"email": race_email.upper().replace("@EXAMPLE.COM", "@example.com"), "password": PASSWORD},
    ]
    async with app.router.lifespan_context(app), client_for(app) as http:
        responses = await asyncio.gather(*(http.post(SIGNUP, json=body) for body in bodies))
    assert [r.status_code for r in responses] == [202, 202]
    assert responses[0].json() == responses[1].json()
    async with AsyncSession(db_engine) as session:
        count = await session.execute(select(func.count()).where(User.email == race_email))
    assert count.scalar_one() == 1


async def test_s3_4_20_a_password_over_the_rules_is_still_just_wrong_at_login(
    db: AsyncSession, db_connection: AsyncConnection
) -> None:
    long_password = "L" * 129  # over the 128-character rule, under the 1024 input cap
    async with api_client(db_connection) as http:
        email = _email()
        await _registered(http, email)
        response = await _login(http, email, long_password)
    assert (response.status_code, response.json()["code"]) == (401, "auth.invalid_credentials")
    assert (await _must_user(db, email)).failed_login_count == 1


@pytest.mark.parametrize(("length", "status"), [(200, 202), (201, 422)])
async def test_s3_4_21_full_name_is_capped_at_200_characters(
    db: AsyncSession, db_connection: AsyncConnection, length: int, status: int
) -> None:
    email = _email()
    body = {"email": email, "password": PASSWORD, "full_name": "N" * length}
    async with api_client(db_connection) as http:
        response = await http.post(SIGNUP, json=body)
    assert response.status_code == status
    assert (await _user(db, email) is not None) == (status == 202)


async def test_s3_4_22_token_and_account_answers_are_never_cached(
    db_connection: AsyncConnection,
) -> None:
    async with api_client(db_connection) as http:
        email = _email()
        signup = await http.post(SIGNUP, json={"email": email, "password": PASSWORD})
        login = await _login(http, email)
        tokens = login.json()
        answers = [
            signup,
            login,
            await http.post(
                "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
            ),
        ]
        bearer = {"Authorization": f"Bearer {answers[-1].json()['access_token']}"}
        answers += [
            await http.get("/api/v1/me", headers=bearer),
            await http.get("/api/v1/me/sessions", headers=bearer),
            await http.post("/api/v1/auth/logout", headers=bearer),
        ]
    for answer in answers:
        assert answer.is_success, answer.request.url
        assert answer.headers["cache-control"] == "no-store", answer.request.url
        assert answer.headers["pragma"] == "no-cache"


async def test_s3_4_23_disabled_signup_is_not_advertised(db_connection: AsyncConnection) -> None:
    async with api_client(db_connection, auth=AuthSettings(signup_enabled=False)) as http:
        hidden = (await http.get("/openapi.json")).json()["paths"]
    async with api_client(db_connection) as http:
        shown = (await http.get("/openapi.json")).json()["paths"]
    assert SIGNUP not in hidden
    assert SIGNUP in shown
    assert LOGIN in hidden


@pytest.mark.xfail(
    strict=True,
    reason="Known gap, roadmap step 6: until email verification gates login, signing up "
    "with an email and then logging in with that password shows whether the email was free",
)
async def test_s3_4_24_signup_then_login_does_not_reveal_whether_the_email_was_free(
    db_connection: AsyncConnection,
) -> None:
    async with api_client(db_connection) as http:
        email = _email()
        await _registered(http, email)
        response = await _login(http, email)
    assert response.status_code == 401  # refused until the address is verified (step 6)
