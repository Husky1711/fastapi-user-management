"""Declarative base, column types and mixins shared by every model."""

import uuid
from datetime import datetime
from typing import Any, ClassVar

from sqlalchemy import DateTime, Dialect, FetchedValue, MetaData, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import TypeDecorator

# Deterministic constraint names, so Alembic can find (and drop) every constraint by name.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_N_label)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_N_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}
POSTGRES_MAX_IDENTIFIER = 63


class AwareDateTime(TypeDecorator[datetime]):
    """`timestamptz` that refuses naive datetimes instead of guessing their time zone."""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is not None and value.tzinfo is None:
            msg = "naive datetime; use app.core.clock.now()"
            raise ValueError(msg)
        return value


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)
    type_annotation_map: ClassVar[dict[Any, Any]] = {datetime: AwareDateTime()}
    # Read server-generated values (defaults, trigger-set `updated_at`) back with RETURNING
    # after INSERT and UPDATE, so async code never triggers a lazy load.
    __mapper_args__ = {"eager_defaults": True}  # noqa: RUF012 - declared by DeclarativeBase


class UUIDPrimaryKey:
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)


class Timestamps:
    """`created_at` / `updated_at` set by the database (`updated_at` by a trigger)."""

    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), server_onupdate=FetchedValue()
    )
