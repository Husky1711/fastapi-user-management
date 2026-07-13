"""Backward-compatible re-exports for auth, users, and password schemas.

Prefer importing from ``schemas.auth``, ``schemas.users``, or ``schemas.password``.
"""

from schemas.auth import (  # noqa: F401
    ErrorResponse,
    HealthCheckResponse,
    Login2FARequest,
    LogoutResponse,
    RateLimitResponse,
    RefreshTokenRequest,
    SessionInfo,
    SuccessResponse,
    TokenData,
    TokenResponse,
    TokenType,
    TwoFactorRequiredResponse,
    UserSigninRequest,
    UserSignupRequest,
    ValidationErrorResponse,
)
from schemas.password import (  # noqa: F401
    PasswordChangeRequest,
    PasswordChangeResponse,
    PasswordResetConfirm,
    PasswordResetConfirmResponse,
    PasswordResetRequest,
    PasswordResetResponse,
)
from schemas.users import (  # noqa: F401
    AdminCreateUserRequest,
    AdminCreateUserResponse,
    AdminUpdateUserRequest,
    AdminUpdateUserResponse,
    OrganizationUsersListResponse,
    PaginationParams,
    SelfUserListResponse,
    SuperAdminUsersResponse,
    UserDetailResponse,
    UserListItem,
    UserProfileUpdate,
    UserProfileUpdateResponse,
    UserResponse,
    UserRole,
    UserSearchParams,
    UsersListResponse,
    UserStatus,
)

# Re-export — source of truth is services.users.role_policy
from services.users.role_policy import RoleHierarchyValidator  # noqa: E402,F401
