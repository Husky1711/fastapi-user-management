"""PostgreSQL engine, session factory and the one way to run a transaction."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import DatabaseSettings


def create_engine(settings: DatabaseSettings) -> AsyncEngine:
    return create_async_engine(
        settings.url.get_secret_value(),
        pool_size=settings.pool_size,
        max_overflow=settings.max_overflow,
        pool_timeout=settings.pool_timeout_seconds,
        pool_pre_ping=True,
        echo=settings.echo,
        connect_args={"timeout": settings.connect_timeout_seconds},
    )


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    # expire_on_commit=False: objects stay readable after commit (no lazy reload in async code).
    # autoflush=False: queries never write half-built objects behind the service's back.
    return async_sessionmaker(engine, expire_on_commit=False, autoflush=False)


@asynccontextmanager
async def transaction(session: AsyncSession) -> AsyncIterator[None]:
    """The service's unit of work: commit if the block succeeds, roll back if it raises.

    Request dependencies (current user, permission checks) read through the same session
    first, and that read autobegins a transaction; the unit of work then continues it, so the
    dependency's reads and the service's writes are one consistent transaction. Call this once
    per service method; it is not reentrant.

    A rollback expires every object loaded in the session (SQLAlchemy behaviour): after a
    failed unit of work, don't read attributes of objects loaded before it.
    """
    if not session.in_transaction():
        await session.begin()
    try:
        yield
        await session.commit()  # a failed commit is rolled back below too
    except BaseException:
        await session.rollback()
        raise


async def ping_database(engine: AsyncEngine) -> None:
    async with engine.connect() as connection:
        await connection.execute(text("SELECT 1"))
