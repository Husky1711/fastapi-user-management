"""Operator commands.

    echo "$ADMIN_PASSWORD" | python -m app.cli create-admin --email ops@example.com

The password is read from standard input (or prompted for, without echo, on a terminal) and
never accepted as an argument: arguments end up in shell history and process lists.
"""

import argparse
import asyncio
import getpass
import sys
from typing import TextIO

from sqlalchemy.exc import DBAPIError

from app.core.config import Settings, get_settings
from app.core.emails import InvalidEmail
from app.core.errors import Conflict
from app.core.redaction import mask_email
from app.core.security import WeakPassword
from app.infra.database import create_engine, create_session_factory
from app.services.admin import create_platform_admin

EXIT_OK = 0
EXIT_FAILED = 1
EXIT_INVALID_INPUT = 2  # same code argparse uses for usage errors
UNDEFINED_TABLE = "42P01"  # PostgreSQL SQLSTATE: the schema hasn't been migrated


def database_problem(error: OSError | DBAPIError) -> str:
    """What to tell the operator; only a missing table means "run migrations"."""
    if isinstance(error, DBAPIError) and _sqlstate(error) == UNDEFINED_TABLE:
        return (
            "error: the database schema is missing or out of date; run migrations first "
            "(alembic upgrade head)."
        )
    return f"error: cannot use the database ({type(error).__name__})."


def _sqlstate(error: DBAPIError) -> str | None:
    """SQLSTATE of the driver error (asyncpg keeps it on the original exception)."""
    for candidate in (error.orig, getattr(error.orig, "__cause__", None)):
        code = getattr(candidate, "sqlstate", None)
        if isinstance(code, str):
            return code
    return None


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser(
        "create-admin", help="Create a platform admin (password read from standard input)."
    )
    create.add_argument("--email", required=True)
    return parser


def _read_password(stdin: TextIO) -> str:
    """Only the line ending is removed: spaces are valid password characters."""
    if stdin.isatty():
        return getpass.getpass("Password: ")
    return stdin.readline().rstrip("\r\n")


async def _create_admin(
    email: str, password: str, settings: Settings, out: TextIO, err: TextIO
) -> int:
    engine = create_engine(settings.database)
    try:
        async with create_session_factory(engine)() as session:
            user = await create_platform_admin(session, email=email, password=password)
    except (InvalidEmail, WeakPassword) as error:
        print(f"error: {error}", file=err)
        return EXIT_INVALID_INPUT
    except Conflict:
        print("error: a user with this email already exists; nothing was changed.", file=err)
        return EXIT_FAILED
    except (OSError, DBAPIError) as error:
        print(database_problem(error), file=err)
        return EXIT_FAILED
    finally:
        await engine.dispose()
    print(f"Created platform admin {mask_email(user.email)} (id {user.id}).", file=out)
    return EXIT_OK


async def run(
    argv: list[str],
    *,
    stdin: TextIO,
    out: TextIO,
    err: TextIO,
    settings: Settings | None = None,
) -> int:
    try:
        args = _parser().parse_args(argv)
    except SystemExit as exit_:
        return int(exit_.code or 0)
    password = _read_password(stdin)
    return await _create_admin(args.email, password, settings or get_settings(), out, err)


def main() -> None:
    sys.exit(asyncio.run(run(sys.argv[1:], stdin=sys.stdin, out=sys.stdout, err=sys.stderr)))


if __name__ == "__main__":
    main()
