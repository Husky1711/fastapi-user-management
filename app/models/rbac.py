"""Roles and permissions. Permissions are data; roles group them (ADR on RBAC)."""

import uuid

from sqlalchemy import CheckConstraint, Column, ForeignKey, Index, Table, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, Timestamps, UUIDPrimaryKey

role_permissions = Table(
    "role_permissions",
    Base.metadata,
    Column("role_id", ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    Column(
        "permission_key",
        ForeignKey("permissions.key", ondelete="CASCADE", onupdate="CASCADE"),
        primary_key=True,
    ),
    Index("ix_role_permissions_permission_key", "permission_key"),
)


class Permission(Base):
    __tablename__ = "permissions"
    __table_args__ = (CheckConstraint("key ~ '^[a-z]+:[a-z_]+$'", name="key_format"),)

    key: Mapped[str] = mapped_column(Text, primary_key=True)
    description: Mapped[str] = mapped_column(Text)


class Role(UUIDPrimaryKey, Timestamps, Base):
    """`organization_id` NULL means a system role (owner, admin, member) shared by every org."""

    __tablename__ = "roles"
    __table_args__ = (
        # NULLS NOT DISTINCT: two system roles (organization_id NULL) can't share a key either.
        UniqueConstraint("organization_id", "key", postgresql_nulls_not_distinct=True),
        CheckConstraint("key ~ '^[a-z][a-z0-9_]{1,49}$'", name="key_format"),
        CheckConstraint("char_length(name) BETWEEN 1 AND 100", name="name_length"),
    )

    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE")
    )
    key: Mapped[str] = mapped_column(Text)
    name: Mapped[str] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)

    permissions: Mapped[list[Permission]] = relationship(
        secondary=role_permissions, lazy="raise", order_by=Permission.key
    )

    @property
    def is_system(self) -> bool:
        return self.organization_id is None
