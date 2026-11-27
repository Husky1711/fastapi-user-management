"""Section 2.6: the `create-admin` command and the service behind it."""

import asyncio
import io
import logging
import uuid
from collections.abc import AsyncIterator
from typing import Annotated

import pytest
from fastapi import APIRouter, Depends
from pydantic import SecretStr
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app import cli
from app.core import clock
from app.core.config import DatabaseSettings
from app.core.deps import DbSession
from app.core.errors import Conflict
from app.core.security import verify_password
from app.main import create_app
from app.models import User, UserStatus
from app.repositories import UserRepository
from app.services.admin import create_platform_admin
from tests.db import (
    SERVICE_DATABASE_URL,
    SERVICES,
    UNREACHABLE_DB,
    UNREACHABLE_PASSWORD,
    service_database_settings,
)
from tests.factories import add, new_user
from tests.helpers import check_ok, client_for, make_settings

pytestmark = SERVICES

PASSWORD = "Adm1n-Passw0rd-For-Tests"


class _Terminal(io.StringIO):
    def isatty(self) -> bool:
        return True


async def _run(
    *argv: str,
    stdin: str = f"{PASSWORD}\n",
    database_down: bool = False,
    database: DatabaseSettings | None = None,
) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    if database is None:
        database = UNREACHABLE_DB if database_down else service_database_settings()
    code = await cli.run(
        list(argv),
        stdin=io.StringIO(stdin),
        out=out,
        err=err,
        settings=make_settings(database=database),
    )
    return code, out.getvalue(), err.getvalue()


@pytest.fixture
async def email(db_engine: AsyncEngine) -> AsyncIterator[str]:
    """A unique address; any user created with it is deleted after the test."""
    address = f"ops-{uuid.uuid4().hex[:12]}@example.com"
    yield address
    async with AsyncSession(db_engine) as session, session.begin():
        await session.execute(delete(User).where(User.email == address))


async def _users(engine: AsyncEngine, email: str) -> list[User]:
    async with AsyncSession(engine) as session:
        return list((await session.execute(select(User).where(User.email == email))).scalars())


async def test_s2_6_08_creates_a_verified_platform_admin(
    db_engine: AsyncEngine, email: str
) -> None:
    code, out, err = await _run(
        "create-admin", "--email", email.upper().replace("EXAMPLE.COM", "Example.COM")
    )
    assert (code, err) == (0, "")
    assert "Created platform admin O***@example.com" in out
    (user,) = await _users(db_engine, email)
    assert (user.is_platform_admin, user.email_verified, user.status) == (True, True, "active")
    assert user.password_hash.startswith("$argon2id$")
    assert await verify_password(user.password_hash, PASSWORD)
    assert str(user.id) in out


async def test_s2_6_09_existing_email_changes_nothing(db_engine: AsyncEngine, email: str) -> None:
    assert (await _run("create-admin", "--email", email))[0] == 0
    (before,) = await _users(db_engine, email)
    code, out, err = await _run("create-admin", "--email", email, stdin="Another-Long-Passw0rd\n")
    assert (code, out) == (1, "")
    assert "already exists" in err
    (after,) = await _users(db_engine, email)
    assert after.password_hash == before.password_hash


async def test_s2_6_09_email_of_a_deleted_user_is_still_taken(db: AsyncSession) -> None:
    gone = new_user(status=UserStatus.DELETED, deleted_at=clock.now())
    await add(db, gone)
    email, gone_id = gone.email, gone.id  # the failed transaction's rollback expires `gone`
    await db.commit()  # created by an earlier request (else the failed unit of work undoes it)
    with pytest.raises(Conflict):
        await create_platform_admin(db, email=email, password=PASSWORD)
    (only,) = (await db.execute(select(User.id).where(User.email == email))).scalars()
    assert only == gone_id


async def test_s2_6_10_password_is_only_read_from_stdin_and_never_printed(
    email: str, caplog: pytest.LogCaptureFixture, capsys: pytest.CaptureFixture[str]
) -> None:
    code, _, _ = await _run("create-admin", "--email", email, "--password", PASSWORD)
    assert code == 2  # no such option
    capsys.readouterr()  # argparse echoes the rejected argument back to the person who typed it
    with caplog.at_level(logging.DEBUG):
        code, out, err = await _run("create-admin", "--email", email)
    assert code == 0
    printed = out + err + capsys.readouterr().err + caplog.text
    assert PASSWORD not in printed
    assert email not in printed  # only the masked address


async def test_s2_6_10_on_a_terminal_the_password_is_prompted_without_echo(
    email: str, monkeypatch: pytest.MonkeyPatch, db_engine: AsyncEngine
) -> None:
    prompts: list[str] = []

    def fake_getpass(prompt: str) -> str:
        prompts.append(prompt)
        return PASSWORD

    monkeypatch.setattr("getpass.getpass", fake_getpass)
    out, err = io.StringIO(), io.StringIO()
    settings = make_settings(database=service_database_settings())
    code = await cli.run(
        ["create-admin", "--email", email], stdin=_Terminal(), out=out, err=err, settings=settings
    )
    assert (code, prompts) == (0, ["Password: "])
    assert len(await _users(db_engine, email)) == 1


@pytest.mark.parametrize(
    ("email_arg", "stdin", "message"),
    [
        ("not-an-email", f"{PASSWORD}\n", "email address"),
        ("ops@example.com", "short\n", "at least 12"),
        ("ops@example.com", "\n", "at least 12"),
        ("ops@example.com", "", "at least 12"),
    ],
)
async def test_s2_6_11_invalid_input_exits_2_and_creates_nothing(
    db_engine: AsyncEngine, email_arg: str, stdin: str, message: str
) -> None:
    before = [u.id for u in await _users(db_engine, "ops@example.com")]
    code, out, err = await _run("create-admin", "--email", email_arg, stdin=stdin)
    assert (code, out) == (2, "")
    assert message in err
    assert [u.id for u in await _users(db_engine, "ops@example.com")] == before


async def test_s2_6_13_database_down_exits_1_without_leaking(email: str) -> None:
    code, out, err = await _run("create-admin", "--email", email, database_down=True)
    assert (code, out) == (1, "")
    assert "cannot use the database" in err
    assert PASSWORD not in err
    assert UNREACHABLE_PASSWORD not in err


async def test_s2_6_14_concurrent_creates_with_one_email_give_exactly_one_conflict(
    db_engine: AsyncEngine, email: str
) -> None:
    async def create(variant: str) -> User:
        async with AsyncSession(db_engine, expire_on_commit=False) as session:
            return await create_platform_admin(session, email=variant, password=PASSWORD)

    results = await asyncio.gather(
        create(email),
        create(email.upper().replace("@EXAMPLE.COM", "@example.com")),
        return_exceptions=True,
    )
    assert sum(isinstance(r, User) for r in results) == 1
    assert sum(isinstance(r, Conflict) for r in results) == 1
    assert len(await _users(db_engine, email)) == 1


async def test_s2_6_13_database_without_the_schema_says_to_run_migrations(email: str) -> None:
    # The server's default "postgres" database exists but has none of our tables.
    url = SERVICE_DATABASE_URL.rsplit("/", 1)[0] + "/postgres"
    code, out, err = await _run(
        "create-admin", "--email", email, database=DatabaseSettings(url=SecretStr(url))
    )
    assert (code, out) == (1, "")
    assert "run migrations first" in err


async def test_s2_6_13_unresponsive_database_host_gives_up_after_the_connect_timeout(
    email: str,
) -> None:
    # 10.255.255.1 is not routable: packets are dropped, so only the timeout ends the wait.
    blackhole = DatabaseSettings(
        url=SecretStr(f"postgresql+asyncpg://app:{UNREACHABLE_PASSWORD}@10.255.255.1:5432/app"),
        connect_timeout_seconds=0.5,
    )
    started = asyncio.get_running_loop().time()
    code, out, err = await _run("create-admin", "--email", email, database=blackhole)
    assert asyncio.get_running_loop().time() - started < 5  # not asyncpg's 60 s default
    assert (code, out) == (1, "")
    assert "cannot use the database" in err
    assert UNREACHABLE_PASSWORD not in err


def _admin_router() -> APIRouter:
    """Stands for a real route: a dependency reads the caller first (like get_current_user),
    then the one service call runs its unit of work on the same session."""
    router = APIRouter()

    async def caller(session: DbSession) -> User | None:
        return await UserRepository(session).get_by_email("caller@example.com")

    @router.post("/_test/admins")
    async def create(
        body: dict[str, str], session: DbSession, _: Annotated[User | None, Depends(caller)]
    ) -> dict[str, str]:
        user = await create_platform_admin(session, email=body["email"], password=body["password"])
        return {"id": str(user.id)}

    return router


async def test_s2_6_15_over_http_rules_and_conflicts_are_problem_responses(
    db_engine: AsyncEngine, email: str
) -> None:
    settings = make_settings(database=service_database_settings())
    app = create_app(settings, health_checks={"database": check_ok}, api_routers=[_admin_router()])
    path = "/api/v1/_test/admins"
    async with app.router.lifespan_context(app), client_for(app) as http:
        created = await http.post(path, json={"email": email, "password": PASSWORD})
        again = await http.post(path, json={"email": email, "password": PASSWORD})
        bad_email = await http.post(path, json={"email": "nope", "password": PASSWORD})
        weak = await http.post(path, json={"email": email, "password": "short"})
    assert created.status_code == 200
    (user,) = await _users(db_engine, email)
    assert created.json() == {"id": str(user.id)}
    assert (again.status_code, again.json()["code"]) == (409, "user.email_taken")
    assert (bad_email.status_code, bad_email.json()["code"]) == (422, "user.email_invalid")
    assert (weak.status_code, weak.json()["code"]) == (422, "user.password_weak")
    assert PASSWORD not in again.text + bad_email.text + weak.text
