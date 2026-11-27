"""Alembic environment: async engine, URL from the app settings, models as the target."""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.models import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)


# Several replicas or init containers may run `upgrade head` at the same deploy. The first
# takes this lock; the others wait, then find the database already at head and do nothing.
# The lock belongs to the connection: run migrations directly against PostgreSQL, not
# through PgBouncer in transaction-pooling mode.
MIGRATION_LOCK_ID = 727_100_001  # arbitrary, constant for this application


def _run(connection: Connection) -> None:
    connection.execute(text("SELECT pg_advisory_lock(:id)"), {"id": MIGRATION_LOCK_ID})
    connection.commit()  # the lock is held by the connection; Alembic then runs its own
    try:
        _migrate(connection)
    finally:
        connection.execute(text("SELECT pg_advisory_unlock(:id)"), {"id": MIGRATION_LOCK_ID})
        connection.commit()


def _migrate(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=Base.metadata,
        compare_type=True,
        transaction_per_migration=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def _run_online() -> None:
    database = get_settings().database
    engine = create_async_engine(
        database.url.get_secret_value(),
        poolclass=NullPool,
        connect_args={"timeout": database.connect_timeout_seconds},
    )
    try:
        async with engine.connect() as connection:
            await connection.run_sync(_run)
    finally:
        await engine.dispose()


if context.is_offline_mode():
    raise SystemExit("Offline (SQL script) migrations are not supported; run against a database.")
asyncio.run(_run_online())
