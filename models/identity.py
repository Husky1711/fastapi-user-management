"""Identity models: organizations, users, refresh tokens."""

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from utils.database import Base


class Organization(Base):
    __tablename__ = "organizations"

    id = Column(Integer, primary_key=True, index=True)
    # Active-only uniqueness: uq_organizations_name_active / uq_organizations_slug_active.
    name = Column(String(100), nullable=False, index=True)
    slug = Column(String(100), nullable=False, index=True)
    description = Column(Text, nullable=True)
    status = Column(String(20), default="active")  # active | inactive | suspended (DB ENUM)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    deleted_at = Column(DateTime(timezone=True), nullable=True, index=True)
    deleted_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    users = relationship(
        "User",
        back_populates="organization",
        foreign_keys="[User.organization_id]",
    )


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token_hash = Column(String(255), unique=True, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    device_info = Column(Text, nullable=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    is_revoked = Column(Boolean, nullable=False, default=False, server_default="0")
    revoked_at = Column(DateTime(timezone=True), nullable=True)

    user = relationship("User", back_populates="refresh_tokens")


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    # Uniqueness for active rows is enforced by functional indexes
    # uq_users_username_active / uq_users_email_active (deleted_at IS NULL).
    username = Column(String(50), index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    email = Column(String(255), index=True, nullable=False)
    status = Column(String(20), default="active")
    phone_number = Column(String(20), default="0000000000")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    last_login = Column(DateTime(timezone=True), nullable=True)
    locked_until = Column(DateTime(timezone=True), nullable=True)

    is_2fa_enabled = Column(Boolean, nullable=False, default=False, server_default="0", index=True)
    two_factor_secret = Column(String(255), nullable=True)
    backup_codes = Column(JSON, nullable=True)
    backup_codes_generated_at = Column(DateTime(timezone=True), nullable=True)
    failed_login_attempts = Column(Integer, nullable=False, default=0, server_default="0")
    email_verified_at = Column(DateTime(timezone=True), nullable=True)
    password_changed_at = Column(DateTime(timezone=True), nullable=True)
    deleted_at = Column(DateTime(timezone=True), nullable=True, index=True)
    deleted_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    role = Column(String(20), default="user")
    organization_id = Column(
        Integer, ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    manager_id = Column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )

    refresh_tokens = relationship(
        "RefreshToken", back_populates="user", cascade="all, delete-orphan"
    )
    organization = relationship(
        "Organization",
        back_populates="users",
        foreign_keys=[organization_id],
    )
    manager = relationship(
        "User",
        remote_side="User.id",
        foreign_keys=[manager_id],
        back_populates="direct_reports",
    )
    direct_reports = relationship(
        "User",
        back_populates="manager",
        foreign_keys=[manager_id],
    )
