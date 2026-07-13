"""Password reset and change schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from config.settings import settings
from utils.datetime_utc import utc_now


def validate_password_against_policy(value: str) -> str:
    """Enforce configured password policy rules."""
    policy = settings.password_policy
    if len(value) < policy.min_password_length:
        raise ValueError(f"Password must be at least {policy.min_password_length} characters")
    if len(value) > policy.max_password_length:
        raise ValueError(f"Password must be at most {policy.max_password_length} characters")
    if policy.require_uppercase and not any(c.isupper() for c in value):
        raise ValueError("Password must contain at least one uppercase letter")
    if policy.require_lowercase and not any(c.islower() for c in value):
        raise ValueError("Password must contain at least one lowercase letter")
    if policy.require_digits and not any(c.isdigit() for c in value):
        raise ValueError("Password must contain at least one digit")
    if policy.require_special_chars and not any(not c.isalnum() for c in value):
        raise ValueError("Password must contain at least one special character")
    return value


class PasswordResetRequest(BaseModel):
    """Schema for password reset request"""

    email: EmailStr = Field(..., description="Email address to send reset link")

    model_config = ConfigDict(use_enum_values=True)


class PasswordResetResponse(BaseModel):
    """Schema for password reset response"""

    success: bool = Field(..., description="Whether reset request was successful")
    message: str = Field(..., description="Success or error message")
    reset_token: Optional[str] = Field(None, description="Reset token (for testing)")
    expires_in_minutes: int = Field(default=15, description="Token expiration time in minutes")
    timestamp: datetime = Field(default_factory=utc_now, description="Request timestamp")
    correlation_id: Optional[str] = Field(None, description="Request correlation ID")

    model_config = ConfigDict(use_enum_values=True)


class PasswordResetConfirm(BaseModel):
    """Schema for password reset confirmation"""

    token: str = Field(..., min_length=32, max_length=64, description="Reset token")
    new_password: str = Field(..., min_length=8, max_length=100, description="New password")

    model_config = ConfigDict(use_enum_values=True)

    @field_validator("new_password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.islower() for c in v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        return v


class PasswordResetConfirmResponse(BaseModel):
    """Schema for password reset confirmation response"""

    success: bool = Field(..., description="Whether password reset was successful")
    message: str = Field(..., description="Success or error message")
    timestamp: datetime = Field(default_factory=utc_now, description="Reset timestamp")
    correlation_id: Optional[str] = Field(None, description="Request correlation ID")

    model_config = ConfigDict(use_enum_values=True)


class PasswordChangeRequest(BaseModel):
    """Schema for password change request"""

    current_password: str = Field(..., description="Current password")
    new_password: str = Field(..., min_length=1, max_length=200, description="New password")

    model_config = ConfigDict(use_enum_values=True)

    @field_validator("new_password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        return validate_password_against_policy(v)


class PasswordChangeResponse(BaseModel):
    """Schema for password change response"""

    success: bool = Field(..., description="Whether password change was successful")
    message: str = Field(..., description="Success or error message")
    timestamp: datetime = Field(default_factory=utc_now, description="Change timestamp")
    correlation_id: Optional[str] = Field(None, description="Request correlation ID")

    model_config = ConfigDict(use_enum_values=True)
