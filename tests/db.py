"""Helpers for tests that need the real PostgreSQL (CI service or `make run`)."""

import os
import re
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import pytest
from pydantic import SecretStr
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import DatabaseSettings

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
