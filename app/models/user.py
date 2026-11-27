"""Users and what belongs only to them: sessions and one-time tokens."""

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import CheckConstraint, ForeignKey, Index, LargeBinary, Text, false, func, text
from sqlalchemy.dialects.postgresql import CITEXT, INET
from sqlalchemy.orm import Mapped, mapped_column

from app.core.client import USER_AGENT_MAX_LENGTH
from app.core.emails import EMAIL_MAX_LENGTH
from app.models.base import Base, Timestamps, UUIDPrimaryKey, text_enum, utc_now

TOKEN_HASH_BYTES = 32  # SHA-256 digest; the token itself is never stored


class UserStatus(StrEnum):
    ACTIVE = "active"
    DISABLED = "disabled"
    DELETED = "deleted"


class RevokeReason(StrEnum):
    ROTATED = "rotated"  # replaced by a refresh; presenting it again means it was stolen
    LOGOUT = "logout"
    LOGOUT_ALL = "logout_all"
    REVOKED = "revoked"  # ended by the user from their session list
    REPLACED = "replaced"  # ended by the session strategy at a new login
    PASSWORD_CHANGED = "password_changed"  # noqa: S105 - a reason name, not a password
    REUSE_DETECTED = "reuse_detected"


class TokenPurpose(StrEnum):
    VERIFY_EMAIL = "verify_email"
    RESET_PASSWORD = "reset_password"  # noqa: S105 - a purpose name, not a password


def email_length_check() -> CheckConstraint:
    return CheckConstraint(
        f"char_length(email) BETWEEN 3 AND {EMAIL_MAX_LENGTH}", name="email_length"
    )


def token_hash_check() -> CheckConstraint:
    return CheckConstraint(f"octet_length(token_hash) = {TOKEN_HASH_BYTES}", name="token_hash_size")


class User(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "users"
    __table_args__ = (
        email_length_check(),
        CheckConstraint("char_length(full_name) <= 200", name="full_name_length"),
        CheckConstraint("failed_login_count >= 0", name="failed_login_count_not_negative"),
        CheckConstraint(
            "(status = 'deleted') = (deleted_at IS NOT NULL)", name="deleted_status_has_deleted_at"
        ),
    )

    email: Mapped[str] = mapped_column(CITEXT, unique=True)
    password_hash: Mapped[str] = mapped_column(Text)
    full_name: Mapped[str | None] = mapped_column(Text)
    email_verified: Mapped[bool] = mapped_column(default=False, server_default=false())
    status: Mapped[UserStatus] = mapped_column(
        text_enum(UserStatus, "status"), default=UserStatus.ACTIVE, server_default="active"
    )
    is_platform_admin: Mapped[bool] = mapped_column(default=False, server_default=false())
    failed_login_count: Mapped[int] = mapped_column(default=0, server_default="0")
    locked_until: Mapped[datetime | None]
    last_login_at: Mapped[datetime | None]
    deleted_at: Mapped[datetime | None]


class UserSession(UUIDPrimaryKey, Timestamps, Base):
    """One refresh token. A login starts a family (`family_id`, the access token's `sid`);
    each refresh revokes the row (`rotated`) and adds the next one to the same family."""

    __tablename__ = "sessions"
    __table_args__ = (
        token_hash_check(),
        CheckConstraint("expires_at > created_at", name="expires_after_created"),
        CheckConstraint(
            f"char_length(user_agent) <= {USER_AGENT_MAX_LENGTH}", name="user_agent_length"
        ),
        CheckConstraint(
            "(revoked_at IS NULL) = (revoked_reason IS NULL)", name="revoked_reason_set"
        ),
        CheckConstraint("family_started_at <= created_at", name="family_started_first"),
        # Full index (not partial): deleting a user must also find revoked sessions.
        Index("ix_sessions_user_id", "user_id"),
        # At most one usable token per family: two concurrent refreshes can't both succeed.
        Index(
            "uq_sessions_family_id_active",
            "family_id",
            unique=True,
            postgresql_where=text("revoked_at IS NULL"),
        ),
        Index("ix_sessions_family_id", "family_id"),
        Index("ix_sessions_expires_at", "expires_at"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    family_id: Mapped[uuid.UUID]
    family_started_at: Mapped[datetime]  # first login of the family; caps refreshing
    token_hash: Mapped[bytes] = mapped_column(LargeBinary, unique=True)
    expires_at: Mapped[datetime]
    revoked_at: Mapped[datetime | None]
    revoked_reason: Mapped[RevokeReason | None] = mapped_column(
        text_enum(RevokeReason, "revoked_reason")
    )
    last_used_at: Mapped[datetime | None]
    ip: Mapped[str | None] = mapped_column(INET)
    user_agent: Mapped[str | None] = mapped_column(Text)


class OneTimeToken(UUIDPrimaryKey, Base):
    """Email verification and password reset tokens (single use)."""

    __tablename__ = "one_time_tokens"
    __table_args__ = (
        token_hash_check(),
        CheckConstraint("expires_at > created_at", name="expires_after_created"),
        Index("ix_one_time_tokens_user_id_purpose", "user_id", "purpose"),
        Index("ix_one_time_tokens_expires_at", "expires_at"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    purpose: Mapped[TokenPurpose] = mapped_column(text_enum(TokenPurpose, "purpose"))
    token_hash: Mapped[bytes] = mapped_column(LargeBinary, unique=True)
    created_at: Mapped[datetime] = mapped_column(default=utc_now, server_default=func.now())
    expires_at: Mapped[datetime]
    used_at: Mapped[datetime | None]
