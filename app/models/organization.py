"""Organizations, their members and invitations."""

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    LargeBinary,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import CITEXT
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, Timestamps, UUIDPrimaryKey, text_enum
from app.models.rbac import Role
from app.models.user import User, email_length_check, token_hash_check

SLUG_PATTERN = "^[a-z0-9]+(-[a-z0-9]+)*$"
SLUG_MAX_LENGTH = 63


class OrganizationStatus(StrEnum):
    ACTIVE = "active"
    SUSPENDED = "suspended"


class Organization(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "organizations"
    __table_args__ = (
        CheckConstraint("char_length(name) BETWEEN 1 AND 200", name="name_length"),
        CheckConstraint(
            f"slug ~ '{SLUG_PATTERN}' AND char_length(slug) <= {SLUG_MAX_LENGTH}",
            name="slug_format",
        ),
    )

    name: Mapped[str] = mapped_column(Text)
    slug: Mapped[str] = mapped_column(CITEXT, unique=True)
    status: Mapped[OrganizationStatus] = mapped_column(
        text_enum(OrganizationStatus, "status"),
        default=OrganizationStatus.ACTIVE,
        server_default="active",
    )


class Membership(UUIDPrimaryKey, Timestamps, Base):
    """A user's place in an organization. The role must be a system role or one of this org's
    roles (enforced by the `memberships_role_scope` trigger)."""

    __tablename__ = "memberships"
    __table_args__ = (
        UniqueConstraint("user_id", "organization_id"),
        Index("ix_memberships_organization_id_created_at", "organization_id", "created_at"),
        Index("ix_memberships_role_id", "role_id"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE")
    )
    role_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("roles.id", ondelete="RESTRICT"))

    user: Mapped[User] = relationship(lazy="raise")
    organization: Mapped[Organization] = relationship(lazy="raise")
    role: Mapped[Role] = relationship(lazy="raise")


class Invitation(UUIDPrimaryKey, Timestamps, Base):
    """An invitation to join an organization. At most one pending invitation per email per org."""

    __tablename__ = "invitations"
    __table_args__ = (
        token_hash_check(),
        email_length_check(),
        CheckConstraint("expires_at > created_at", name="expires_after_created"),
        CheckConstraint(
            "accepted_at IS NULL OR revoked_at IS NULL", name="not_accepted_and_revoked"
        ),
        Index(
            "uq_invitations_organization_id_email_pending",
            "organization_id",
            "email",
            unique=True,
            postgresql_where=text("accepted_at IS NULL AND revoked_at IS NULL"),
        ),
        # Listing an org's invitations, and the cascade when an org is deleted (the unique
        # index above is partial, so it can't serve either).
        Index("ix_invitations_organization_id_created_at", "organization_id", "created_at"),
        Index("ix_invitations_role_id", "role_id"),
        Index("ix_invitations_invited_by_user_id", "invited_by_user_id"),
        Index("ix_invitations_expires_at", "expires_at"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE")
    )
    email: Mapped[str] = mapped_column(CITEXT)
    role_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("roles.id", ondelete="RESTRICT"))
    invited_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    token_hash: Mapped[bytes] = mapped_column(LargeBinary, unique=True)
    expires_at: Mapped[datetime]
    accepted_at: Mapped[datetime | None]
    revoked_at: Mapped[datetime | None]
