"""Helpers for tests that need the real PostgreSQL (CI service or `make run`)."""

import os

import pytest
from pydantic import SecretStr

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
