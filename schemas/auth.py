"""Authentication, session, and common API response schemas."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from schemas.password import validate_password_against_policy
from schemas.users import UserResponse, UserRole
from utils.datetime_utc import utc_now


class TokenType(str, Enum):
    BEARER = "bearer"


class UserSignupRequest(BaseModel):
    """Schema for user registration request"""

    username: str = Field(..., min_length=3, max_length=50, description="Username must be 3-50 characters")
    password: str = Field(..., min_length=1, max_length=200, description="Password")
    email: EmailStr = Field(..., description="Valid email address")
    organization_id: int = Field(..., ge=1, description="Organization the user belongs to")

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        if not v.replace("_", "").isalnum():
            raise ValueError("Username must contain only alphanumeric characters and underscores")
        return v.lower()

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        return validate_password_against_policy(v)


class UserSigninRequest(BaseModel):
    """Schema for user login request"""

    username: str = Field(..., min_length=3, max_length=50, description="Username")
    # Login accepts any non-empty password; policy rules apply on signup/reset only.
    password: str = Field(..., min_length=1, max_length=100, description="Password")


class Login2FARequest(BaseModel):
    """Complete login after password step when 2FA is enabled."""

    challenge_token: str = Field(..., min_length=16, description="Short-lived 2FA challenge token")
    totp_code: str = Field(..., min_length=6, max_length=8, description="TOTP or backup code")


class TwoFactorRequiredResponse(BaseModel):
    """Returned from POST /login when a second factor is required."""

    requires_2fa: bool = True
    challenge_token: str
    message: str


class RefreshTokenRequest(BaseModel):
    """Schema for refresh token request"""

    refresh_token: str = Field(..., description="Valid refresh token")


class TokenResponse(BaseModel):
    """Schema for authentication token response"""

    access_token: str = Field(..., description="JWT access token")
    refresh_token: Optional[str] = Field(
        None,
        description="Opaque DB-backed refresh token (optional when httpOnly cookie is used)",
    )
    token_type: TokenType = Field(default=TokenType.BEARER, description="Token type")
    expires_in: int = Field(..., description="Access token expiration time in seconds")
    session_info: Optional[Dict[str, Any]] = Field(None, description="Session management information")


class SessionInfo(BaseModel):
    """Auth session = refresh_tokens row (not user_sessions analytics)."""

    id: int = Field(..., description="Auth session ID (refresh_tokens.id)")
    device_info: Optional[str] = Field(None, description="Device information")
    ip_address: Optional[str] = Field(None, description="IP address")
    created_at: datetime = Field(..., description="Session creation time")
    expires_at: datetime = Field(..., description="Session expiration time")
    is_active: bool = Field(..., description="Whether session is active")
    is_current: bool = Field(False, description="True when this is the caller's refresh session")

    model_config = ConfigDict(from_attributes=True)


class ErrorResponse(BaseModel):
    """Schema for error responses"""

    detail: str = Field(..., description="Error message")
    error_code: Optional[str] = Field(None, description="Error code")
    timestamp: datetime = Field(default_factory=utc_now, description="Error timestamp")
    correlation_id: Optional[str] = Field(None, description="Request correlation ID")


class ValidationErrorResponse(BaseModel):
    """Schema for validation error responses"""

    detail: List[Dict[str, Any]] = Field(..., description="Validation error details")
    error_code: str = Field(default="VALIDATION_ERROR", description="Error code")
    timestamp: datetime = Field(default_factory=utc_now, description="Error timestamp")


class SuccessResponse(BaseModel):
    """Schema for success responses"""

    message: str = Field(..., description="Success message")
    timestamp: datetime = Field(default_factory=utc_now, description="Response timestamp")
    correlation_id: Optional[str] = Field(None, description="Request correlation ID")


class LogoutResponse(SuccessResponse):
    """Schema for logout response"""

    message: str = Field(default="Successfully logged out", description="Logout message")


class HealthCheckResponse(BaseModel):
    """Schema for health check response"""

    status: str = Field(default="healthy", description="Service status")
    timestamp: datetime = Field(default_factory=utc_now, description="Check timestamp")
    version: str = Field(default="1.0.0", description="API version")
    environment: str = Field(default="development", description="Environment")


class RateLimitResponse(BaseModel):
    """Schema for rate limit exceeded response"""

    detail: str = Field(default="Rate limit exceeded", description="Rate limit message")
    retry_after: int = Field(..., description="Seconds to wait before retrying")
    limit: int = Field(..., description="Rate limit per window")
    remaining: int = Field(..., description="Remaining requests in current window")
    reset_time: datetime = Field(..., description="When the rate limit resets")


class TokenData(BaseModel):
    """Schema for JWT token payload data"""

    username: Optional[str] = None
    user_id: Optional[int] = None
    role: Optional[UserRole] = None
    organization_id: Optional[int] = None
    email: Optional[str] = None
    exp: Optional[int] = None
    iat: Optional[int] = None


# Re-export UserResponse for callers that import auth responses together
__all__ = [
    "TokenType",
    "UserSignupRequest",
    "UserSigninRequest",
    "Login2FARequest",
    "TwoFactorRequiredResponse",
    "RefreshTokenRequest",
    "TokenResponse",
    "SessionInfo",
    "ErrorResponse",
    "ValidationErrorResponse",
    "SuccessResponse",
    "LogoutResponse",
    "HealthCheckResponse",
    "RateLimitResponse",
    "TokenData",
    "UserResponse",
]
