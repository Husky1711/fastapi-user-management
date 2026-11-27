import os
from collections.abc import AsyncIterator

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from tests.db import SERVICE_DATABASE_URL
from tests.helpers import app_with, check_ok, client_for

APP_ENV_NAMES = frozenset({"ENVIRONMENT", "DEBUG", "APP_NAME", "VERSION"})
APP_ENV_PREFIXES = ("DATABASE__", "REDIS__", "JWT__", "CORS__", "LOG__", "HEALTH__")


@pytest.fixture(autouse=True)
def _isolate_from_shell_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tests must not depend on app settings exported in the developer's shell or in CI."""
    for name in list(os.environ):
        if name in APP_ENV_NAMES or name.startswith(APP_ENV_PREFIXES):
            monkeypatch.delenv(name)


@pytest.fixture
def app() -> FastAPI:
    return app_with(checks={"database": check_ok, "redis": check_ok})


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    async with client_for(app) as http:
        yield http


@pytest.fixture
async def db_engine() -> AsyncIterator[AsyncEngine]:
    """Engine on the real test database (only for tests marked `services`)."""
    engine = create_async_engine(SERVICE_DATABASE_URL, poolclass=NullPool)
    yield engine
    await engine.dispose()


@pytest.fixture
async def db_connection(db_engine: AsyncEngine) -> AsyncIterator[AsyncConnection]:
    """A connection inside a transaction that is rolled back after the test."""
    async with db_engine.connect() as connection:
        transaction = await connection.begin()
        try:
            yield connection
        finally:
            await transaction.rollback()


@pytest.fixture
async def db(db_connection: AsyncConnection) -> AsyncIterator[AsyncSession]:
    """Session whose commits become savepoints of the test's rolled-back transaction."""
    session = AsyncSession(
        bind=db_connection,
        join_transaction_mode="create_savepoint",
        expire_on_commit=False,
        autoflush=False,
    )
    try:
        yield session
    finally:
        await session.close()
