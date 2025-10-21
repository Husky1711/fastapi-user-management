from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum

# Enums for better type safety
class UserRole(str, Enum):
    SUPER_ADMIN = "super_admin"
    ADMIN = "admin"
    USER = "user"

class UserStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    PENDING = "pending"

class TokenType(str, Enum):
    BEARER = "bearer"

# Request Schemas
class UserSignupRequest(BaseModel):
    """Schema for user registration request"""
    username: str = Field(..., min_length=3, max_length=50, description="Username must be 3-50 characters")
    password: str = Field(..., min_length=8, max_length=100, description="Password must be 8-100 characters")
    email: EmailStr = Field(..., description="Valid email address")
    
    @validator('username')
    def validate_username(cls, v):
        if not v.isalnum():
            raise ValueError('Username must contain only alphanumeric characters')
        return v.lower()
    
    @validator('password')
    def validate_password(cls, v):
        if not any(c.isupper() for c in v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not any(c.islower() for c in v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not any(c.isdigit() for c in v):
            raise ValueError('Password must contain at least one digit')
        return v

class UserSigninRequest(BaseModel):
    """Schema for user login request"""
    username: str = Field(..., min_length=3, max_length=50, description="Username")
    password: str = Field(..., min_length=8, max_length=100, description="Password")

class RefreshTokenRequest(BaseModel):
    """Schema for refresh token request"""
    refresh_token: str = Field(..., description="Valid refresh token")

# Response Schemas
class UserResponse(BaseModel):
    """Schema for user information response"""
    id: int = Field(..., description="User ID")
    username: str = Field(..., description="Username")
    email: EmailStr = Field(..., description="Email address")
    role: UserRole = Field(..., description="User role")
    organization_id: int = Field(..., description="Organization ID")
    status: UserStatus = Field(..., description="User status")
    phone_number: Optional[str] = Field(None, description="Phone number")
    created_at: datetime = Field(..., description="Account creation date")
    last_login: Optional[datetime] = Field(None, description="Last login timestamp")
    
    class Config:
        from_attributes = True  # For SQLAlchemy model compatibility

class TokenResponse(BaseModel):
    """Schema for authentication token response"""
    access_token: str = Field(..., description="JWT access token")
    refresh_token: str = Field(..., description="JWT refresh token")
    token_type: TokenType = Field(default=TokenType.BEARER, description="Token type")
    expires_in: int = Field(..., description="Access token expiration time in seconds")
    session_info: Optional[Dict[str, Any]] = Field(None, description="Session management information")

class SessionInfo(BaseModel):
    """Schema for user session information"""
    id: int = Field(..., description="Session ID")
    device_info: Optional[str] = Field(None, description="Device information")
    ip_address: Optional[str] = Field(None, description="IP address")
    created_at: datetime = Field(..., description="Session creation time")
    expires_at: datetime = Field(..., description="Session expiration time")
    is_active: bool = Field(..., description="Whether session is active")
    
    class Config:
        from_attributes = True

class UsersListResponse(BaseModel):
    """Schema for users list response based on role"""
    organization_id: Optional[int] = Field(None, description="Organization ID")
    users: List[UserResponse] = Field(..., description="List of users")
    total_count: int = Field(..., description="Total number of users")
    page: int = Field(default=1, description="Current page number")
    per_page: int = Field(default=50, description="Users per page")

class SuperAdminUsersResponse(BaseModel):
    """Schema for super admin users response (grouped by organization)"""
    organizations: Dict[int, UsersListResponse] = Field(..., description="Users grouped by organization")
    total_users: int = Field(..., description="Total users across all organizations")

class UserDetailResponse(BaseModel):
    """Schema for detailed user information"""
    id: int = Field(..., description="User ID")
    username: str = Field(..., description="Username")
    email: EmailStr = Field(..., description="Email address")
    role: UserRole = Field(..., description="User role")
    organization_id: int = Field(..., description="Organization ID")
    status: UserStatus = Field(..., description="User status")
    phone_number: Optional[str] = Field(None, description="Phone number")
    created_at: datetime = Field(..., description="Account creation date")
    last_login: Optional[datetime] = Field(None, description="Last login timestamp")
    active_sessions: int = Field(..., description="Number of active sessions")

# Error Response Schemas
class ErrorResponse(BaseModel):
    """Schema for error responses"""
    detail: str = Field(..., description="Error message")
    error_code: Optional[str] = Field(None, description="Error code")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Error timestamp")
    correlation_id: Optional[str] = Field(None, description="Request correlation ID")

class ValidationErrorResponse(BaseModel):
    """Schema for validation error responses"""
    detail: List[Dict[str, Any]] = Field(..., description="Validation error details")
    error_code: str = Field(default="VALIDATION_ERROR", description="Error code")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Error timestamp")

# Success Response Schemas
class SuccessResponse(BaseModel):
    """Schema for success responses"""
    message: str = Field(..., description="Success message")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Response timestamp")
    correlation_id: Optional[str] = Field(None, description="Request correlation ID")

class LogoutResponse(SuccessResponse):
    """Schema for logout response"""
    message: str = Field(default="Successfully logged out", description="Logout message")

# Health Check Schema
class HealthCheckResponse(BaseModel):
    """Schema for health check response"""
    status: str = Field(default="healthy", description="Service status")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Check timestamp")
    version: str = Field(default="1.0.0", description="API version")
    environment: str = Field(default="development", description="Environment")

# Rate Limit Response Schema
class RateLimitResponse(BaseModel):
    """Schema for rate limit exceeded response"""
    detail: str = Field(default="Rate limit exceeded", description="Rate limit message")
    retry_after: int = Field(..., description="Seconds to wait before retrying")
    limit: int = Field(..., description="Rate limit per window")
    remaining: int = Field(..., description="Remaining requests in current window")
    reset_time: datetime = Field(..., description="When the rate limit resets")

# Token Data Schema (for internal use)
class TokenData(BaseModel):
    """Schema for JWT token payload data"""
    username: Optional[str] = None
    user_id: Optional[int] = None
    role: Optional[UserRole] = None
    organization_id: Optional[int] = None
    email: Optional[str] = None
    exp: Optional[int] = None
    iat: Optional[int] = None

# Pagination Schema
class PaginationParams(BaseModel):
    """Schema for pagination parameters"""
    page: int = Field(default=1, ge=1, description="Page number (starts from 1)")
    per_page: int = Field(default=50, ge=1, le=100, description="Items per page (max 100)")
    sort_by: Optional[str] = Field(default="created_at", description="Field to sort by")
    sort_order: str = Field(default="desc", pattern="^(asc|desc)$", description="Sort order")

# Search and Filter Schemas
class UserSearchParams(BaseModel):
    """Schema for user search parameters"""
    query: Optional[str] = Field(None, description="Search query")
    role: Optional[UserRole] = Field(None, description="Filter by role")
    status: Optional[UserStatus] = Field(None, description="Filter by status")
    organization_id: Optional[int] = Field(None, description="Filter by organization")
    created_after: Optional[datetime] = Field(None, description="Filter by creation date")
    created_before: Optional[datetime] = Field(None, description="Filter by creation date")
    
    class Config:
        use_enum_values = True