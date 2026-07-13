"""User, admin, and profile request/response schemas."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from utils.datetime_utc import utc_now


class UserRole(str, Enum):
    SUPER_ADMIN = "super_admin"
    ORGANIZATION_ADMIN = "organization_admin"
    ADMIN = "admin"
    USER = "user"


class UserStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    PENDING = "pending"


class UserResponse(BaseModel):
    """Schema for user information response"""

    id: int = Field(..., description="User ID")
    username: str = Field(..., description="Username")
    email: EmailStr = Field(..., description="Email address")
    role: UserRole = Field(..., description="User role")
    organization_id: int = Field(..., description="Organization ID")
    organization_name: Optional[str] = Field(None, description="Organization name")
    status: UserStatus = Field(..., description="User status")
    phone_number: Optional[str] = Field(None, description="Phone number")
    manager_id: Optional[int] = Field(None, description="Reporting manager user ID")
    manager_username: Optional[str] = Field(None, description="Reporting manager username")
    created_at: Optional[datetime] = Field(None, description="Account creation date")
    last_login: Optional[datetime] = Field(None, description="Last login timestamp")

    model_config = ConfigDict(from_attributes=True)


class UserListItem(BaseModel):
    """Compact user row for list endpoints (matches GET /users wire format)."""

    id: int
    username: str
    email: EmailStr
    role: str
    status: str
    phone_number: Optional[str] = None
    manager_id: Optional[int] = None
    manager_username: Optional[str] = None


class OrganizationUsersListResponse(BaseModel):
    """Admin / organization_admin list payload."""

    organization_id: int
    users: List[UserListItem]


class SelfUserListResponse(BaseModel):
    """Regular user list payload (self only)."""

    user: UserListItem


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


class PaginationParams(BaseModel):
    """Schema for pagination parameters"""

    page: int = Field(default=1, ge=1, description="Page number (starts from 1)")
    per_page: int = Field(default=50, ge=1, le=100, description="Items per page (max 100)")
    sort_by: Optional[str] = Field(default="created_at", description="Field to sort by")
    sort_order: str = Field(default="desc", pattern="^(asc|desc)$", description="Sort order")


class UserSearchParams(BaseModel):
    """Schema for user search parameters"""

    query: Optional[str] = Field(None, description="Search query")
    role: Optional[UserRole] = Field(None, description="Filter by role")
    status: Optional[UserStatus] = Field(None, description="Filter by status")
    organization_id: Optional[int] = Field(None, description="Filter by organization")
    created_after: Optional[datetime] = Field(None, description="Filter by creation date")
    created_before: Optional[datetime] = Field(None, description="Filter by creation date")

    model_config = ConfigDict(use_enum_values=True)


class AdminCreateUserRequest(BaseModel):
    """Schema for admin user creation request"""

    username: str = Field(..., min_length=3, max_length=50, description="Username must be 3-50 characters")
    email: EmailStr = Field(..., description="Valid email address")
    password: Optional[str] = Field(
        None,
        min_length=8,
        max_length=100,
        description="Password (optional if auto_generate_password is True)",
    )
    role: UserRole = Field(default=UserRole.USER, description="User role to assign")
    organization_id: Optional[int] = Field(
        None, description="Organization ID (inherited from creator if not specified)"
    )
    phone_number: Optional[str] = Field(None, description="Phone number")
    manager_id: Optional[int] = Field(None, description="Reporting manager (regular users only)")
    send_welcome_email: bool = Field(default=True, description="Send welcome email to new user")
    auto_generate_password: bool = Field(default=True, description="Auto-generate secure password")

    model_config = ConfigDict(use_enum_values=True)

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        if not v.replace("_", "").isalnum():
            raise ValueError("Username must contain only alphanumeric characters and underscores")
        return v.lower()

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            if not any(c.isupper() for c in v):
                raise ValueError("Password must contain at least one uppercase letter")
            if not any(c.islower() for c in v):
                raise ValueError("Password must contain at least one lowercase letter")
            if not any(c.isdigit() for c in v):
                raise ValueError("Password must contain at least one digit")
        return v

    @field_validator("phone_number")
    @classmethod
    def validate_phone_number(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not v.isdigit():
            raise ValueError("Phone number must contain only digits")
        return v


class AdminCreateUserResponse(BaseModel):
    """Schema for admin user creation response"""

    success: bool = Field(..., description="Whether user creation was successful")
    message: str = Field(..., description="Success or error message")
    user: Optional[UserResponse] = Field(None, description="Created user details")
    generated_password: Optional[str] = Field(None, description="Auto-generated password (if applicable)")
    email_sent: bool = Field(default=False, description="Whether welcome email was sent")
    timestamp: datetime = Field(default_factory=utc_now, description="Creation timestamp")
    correlation_id: Optional[str] = Field(None, description="Request correlation ID")

    model_config = ConfigDict(use_enum_values=True)


class AdminUpdateUserRequest(BaseModel):
    """Schema for admin user update request"""

    email: Optional[EmailStr] = Field(None, description="New email address")
    phone_number: Optional[str] = Field(None, description="New phone number")
    role: Optional[UserRole] = Field(None, description="New user role")
    status: Optional[UserStatus] = Field(None, description="New user status")
    manager_id: Optional[int] = Field(None, description="Reporting manager user ID (null clears)")
    organization_id: Optional[int] = Field(None, description="Organization ID (super admin only)")

    model_config = ConfigDict(use_enum_values=True)

    @field_validator("phone_number")
    @classmethod
    def validate_phone_number(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not v.isdigit():
            raise ValueError("Phone number must contain only digits")
        return v


class AdminUpdateUserResponse(BaseModel):
    """Schema for admin user update response"""

    success: bool = Field(..., description="Whether user update was successful")
    message: str = Field(..., description="Success or error message")
    user: Optional[UserResponse] = Field(None, description="Updated user details")
    timestamp: datetime = Field(default_factory=utc_now, description="Update timestamp")
    correlation_id: Optional[str] = Field(None, description="Request correlation ID")

    model_config = ConfigDict(use_enum_values=True)


class UserProfileUpdate(BaseModel):
    """Schema for user profile update"""

    email: Optional[EmailStr] = Field(None, description="New email address")
    phone_number: Optional[str] = Field(None, description="New phone number")

    model_config = ConfigDict(use_enum_values=True)

    @field_validator("phone_number")
    @classmethod
    def validate_phone_number(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not v.isdigit():
            raise ValueError("Phone number must contain only digits")
        return v


class UserProfileUpdateResponse(BaseModel):
    """Schema for user profile update response"""

    success: bool = Field(..., description="Whether profile update was successful")
    message: str = Field(..., description="Success or error message")
    user: Optional[UserResponse] = Field(None, description="Updated user details")
    timestamp: datetime = Field(default_factory=utc_now, description="Update timestamp")
    correlation_id: Optional[str] = Field(None, description="Request correlation ID")

    model_config = ConfigDict(use_enum_values=True)
