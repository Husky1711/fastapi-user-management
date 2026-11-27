"""Helpers for tests that need the real PostgreSQL (CI service or `make run`)."""

import os
import re
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import pytest
from pydantic import SecretStr
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.core.config import DatabaseSettings
from app.models import AuditLog, User

# Read at import time: the autouse fixture in conftest clears app settings from the environment.
SERVICE_DATABASE_URL = os.getenv("DATABASE__URL", "")
SERVICE_REDIS_URL = os.getenv("REDIS__URL", "")

UNREACHABLE_PASSWORD = "unreachable-db-s3cret"
UNREACHABLE_DB = DatabaseSettings(
    # Port 1 on loopback: nothing listens there, so the connection is refused at once.
    url=SecretStr(f"postgresql+asyncpg://app:{UNREACHABLE_PASSWORD}@127.0.0.1:1/app"),
    pool_timeout_seconds=2,
)

# Apply with `pytestmark = SERVICES` (module) or `@pytest.mark.usefixtures` style per test.
SERVICES = [
    pytest.mark.services,
    pytest.mark.skipif(not os.getenv("RUN_SERVICE_TESTS"), reason="needs PostgreSQL and Redis"),
]


def service_database_settings(*, pool_size: int = 5, max_overflow: int = 5) -> DatabaseSettings:
    return DatabaseSettings(
        url=SecretStr(SERVICE_DATABASE_URL), pool_size=pool_size, max_overflow=max_overflow
    )


@asynccontextmanager
async def rejected(session: AsyncSession, reason: str) -> AsyncIterator[None]:
    """The writes in the block must be refused by the database, naming `reason`."""
    # The savepoint has to wrap the caller's whole block, so the block can't be one statement.
    with pytest.raises(IntegrityError, match=re.escape(reason)):  # noqa: PT012
        async with session.begin_nested():
            yield
            await session.flush()


@asynccontextmanager
async def committed_user(engine: AsyncEngine, password_hash: str) -> AsyncIterator[str]:
    """A user committed for real (tests that need several connections at once), and its
    email. The user and its audit rows are removed afterwards (sessions cascade)."""
    email = f"race-{uuid.uuid4().hex[:12]}@example.com"
    async with AsyncSession(engine) as session, session.begin():
        session.add(User(id=uuid.uuid4(), email=email, password_hash=password_hash))
    try:
        yield email
    finally:
        async with AsyncSession(engine) as session, session.begin():
            found = await session.execute(select(User.id).where(User.email == email))
            user_id = found.scalar_one()
            await session.execute(delete(AuditLog).where(AuditLog.actor_user_id == user_id))
            await session.execute(delete(User).where(User.id == user_id))
