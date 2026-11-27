"""Section 2.6: the `create-admin` command and the service behind it."""

import io
import logging
import uuid
from collections.abc import AsyncIterator

import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app import cli
from app.core import clock
from app.core.errors import Conflict
from app.core.security import verify_password
from app.models import User, UserStatus
from app.services.admin import create_platform_admin
from tests.db import SERVICES, UNREACHABLE_DB, service_database_settings
from tests.factories import add, new_user
from tests.helpers import make_settings

pytestmark = SERVICES

PASSWORD = "Adm1n-Passw0rd-For-Tests"


class _Terminal(io.StringIO):
    def isatty(self) -> bool:
        return True


async def _run(
    *argv: str, stdin: str = f"{PASSWORD}\n", database_down: bool = False
) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
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
    with pytest.raises(Conflict):
        await create_platform_admin(db, email=gone.email, password=PASSWORD)
    assert (await db.execute(select(User).where(User.email == gone.email))).scalar_one() is gone


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

    monkeypatch.setattr(cli.getpass, "getpass", fake_getpass)
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
    before = await _users(db_engine, "ops@example.com")
    code, out, err = await _run("create-admin", "--email", email_arg, stdin=stdin)
    assert (code, out) == (2, "")
    assert message in err
    assert await _users(db_engine, "ops@example.com") == before


async def test_s2_6_13_database_down_exits_1_without_leaking(email: str) -> None:
    code, out, err = await _run("create-admin", "--email", email, database_down=True)
    assert (code, out) == (1, "")
    assert "cannot use the database" in err
    assert PASSWORD not in err
    assert UNREACHABLE_DB.url.get_secret_value() not in err
