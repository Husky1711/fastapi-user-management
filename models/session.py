"""Session / credential lifecycle models."""

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.sql import func

from utils.database import Base


class UserSession(Base):
    """User session tracking for security and analytics."""

    __tablename__ = "user_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    session_id = Column(String(255), unique=True, nullable=False, index=True)
    access_token_hash = Column(String(255), nullable=True)
    refresh_token_id = Column(
        Integer, ForeignKey("refresh_tokens.id", ondelete="SET NULL"), nullable=True, index=True
    )
    device_fingerprint = Column(String(255), nullable=True, index=True)
    device_name = Column(String(100), nullable=True)
    device_type = Column(String(50), nullable=True)
    browser_name = Column(String(50), nullable=True)
    browser_version = Column(String(20), nullable=True)
    os_name = Column(String(50), nullable=True)
    os_version = Column(String(20), nullable=True)
    ip_address = Column(String(45), nullable=True, index=True)
    country = Column(String(50), nullable=True)
    city = Column(String(100), nullable=True)
    is_active = Column(Boolean, default=True, index=True)
    last_activity = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)


class PasswordHistory(Base):
    """Password history for security compliance."""

    __tablename__ = "password_history"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    changed_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    change_reason = Column(String(50), nullable=True, index=True)


class PasswordResetToken(Base):
    """Durable hashed password-reset tokens (Redis may mirror for latency)."""

    __tablename__ = "password_reset_tokens"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash = Column(String(255), unique=True, nullable=False, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    used_at = Column(DateTime(timezone=True), nullable=True)
    requested_ip = Column(String(45), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class EmailVerificationToken(Base):
    """Hashed email verification tokens for signup / email change."""

    __tablename__ = "email_verification_tokens"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    email = Column(String(255), nullable=False)
    token_hash = Column(String(255), unique=True, nullable=False, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    verified_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class UserInvitation(Base):
    """Admin-issued invites binding email → org + role until accepted."""

    __tablename__ = "user_invitations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    organization_id = Column(
        Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    email = Column(String(255), nullable=False, index=True)
    role = Column(String(20), nullable=False, default="user")
    token_hash = Column(String(255), unique=True, nullable=False, index=True)
    invited_by = Column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    accepted_at = Column(DateTime(timezone=True), nullable=True)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class LoginAttempt(Base):
    """Track login attempts for security monitoring."""

    __tablename__ = "login_attempts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    username = Column(String(255), nullable=False, index=True)
    ip_address = Column(String(45), nullable=False, index=True)
    user_agent = Column(Text, nullable=True)
    success = Column(Boolean, default=False, index=True)
    failure_reason = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
