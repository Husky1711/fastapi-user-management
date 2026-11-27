"""PostgreSQL engine, session factory and the one way to run a transaction."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
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


_IN_UNIT_OF_WORK = "app.unit_of_work"  # marker in `session.info`


class NestedUnitOfWork(RuntimeError):
    """`transaction()` was entered while one is already running on the same session."""


@asynccontextmanager
async def transaction(session: AsyncSession) -> AsyncIterator[None]:
    """The service's unit of work: commit if the block succeeds, roll back if it raises.

    Request dependencies (current user, permission checks) read through the same session
    first, and those reads autobegin a transaction. The unit of work then runs in a SAVEPOINT
    inside it: on failure only the savepoint is rolled back, which expires only the objects
    changed in the block, so what the dependencies loaded stays readable. On success the
    savepoint is released and the whole transaction committed, before the response is built.

    Not reentrant: one unit of work per service call. A nested call raises instead of
    committing the outer call's half-done work early.
    """
    if session.info.get(_IN_UNIT_OF_WORK):
        raise NestedUnitOfWork("transaction() is already running on this session")
    session.info[_IN_UNIT_OF_WORK] = True
    try:
        if session.in_transaction():
            async with session.begin_nested():
                yield
            await session.commit()
        else:
            async with session.begin():
                yield
    finally:
        session.info.pop(_IN_UNIT_OF_WORK, None)


def is_unique_violation(error: IntegrityError, constraint: str) -> bool:
    """True only for a violation of this unique constraint; every other integrity error is a
    bug and must not be mistaken for "already exists"."""
    return constraint in str(error.orig)


async def end_read(session: AsyncSession) -> None:
    """Finish the current (read-only) transaction now, returning its connection to the pool,
    before slow work such as password hashing (step 2 review R2-03). Loaded objects stay
    readable (`expire_on_commit=False`)."""
    if session.in_transaction():
        await session.commit()


async def ping_database(engine: AsyncEngine) -> None:
    async with engine.connect() as connection:
        await connection.execute(text("SELECT 1"))
