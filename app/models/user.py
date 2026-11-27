"""Users and what belongs only to them: sessions and one-time tokens."""

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import CheckConstraint, ForeignKey, Index, LargeBinary, Text, false, func
from sqlalchemy.dialects.postgresql import CITEXT, INET
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, Timestamps, UUIDPrimaryKey, text_enum

EMAIL_MAX_LENGTH = 254  # RFC 5321 path limit
TOKEN_HASH_BYTES = 32  # SHA-256 digest; the token itself is never stored
USER_AGENT_MAX_LENGTH = 256


class UserStatus(StrEnum):
    ACTIVE = "active"
    DISABLED = "disabled"
    DELETED = "deleted"


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
    deleted_at: Mapped[datetime | None]


class UserSession(UUIDPrimaryKey, Timestamps, Base):
    """A refresh-token session. `family_id` links the tokens of one rotation chain."""

    __tablename__ = "sessions"
    __table_args__ = (
        token_hash_check(),
        CheckConstraint("expires_at > created_at", name="expires_after_created"),
        CheckConstraint(
            f"char_length(user_agent) <= {USER_AGENT_MAX_LENGTH}", name="user_agent_length"
        ),
        # Full index (not partial): deleting a user must also find revoked sessions.
        Index("ix_sessions_user_id", "user_id"),
        Index("ix_sessions_family_id", "family_id"),
        Index("ix_sessions_expires_at", "expires_at"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    family_id: Mapped[uuid.UUID]
    token_hash: Mapped[bytes] = mapped_column(LargeBinary, unique=True)
    expires_at: Mapped[datetime]
    revoked_at: Mapped[datetime | None]
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
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    expires_at: Mapped[datetime]
    used_at: Mapped[datetime | None]
