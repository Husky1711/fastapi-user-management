"""Shared authentication and role dependencies."""

from __future__ import annotations

from typing import Annotated, Callable, FrozenSet, Optional

from fastapi import Depends, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from models.user_model import User
from services.auth import AuthService
from utils.api_errors import APIHTTPException
from utils.database import get_db

bearer_scheme = HTTPBearer()

STAFF_ROLES: FrozenSet[str] = frozenset({"admin", "organization_admin", "super_admin"})


def get_current_user(
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> User:
    """Resolve the authenticated user from JWT (database is source of truth)."""
    user = AuthService.get_current_user(db, credentials.credentials)
    if user is None:
        raise APIHTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            error_code="INVALID_CREDENTIALS",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        from utils.production_logging import user_id_var

        user_id_var.set(user.id)
    except Exception:
        pass
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_roles(*roles: str, error_code: str = "INSUFFICIENT_PERMISSIONS") -> Callable[..., User]:
    """Factory: dependency that allows only the given roles."""
    allowed = frozenset(roles)

    def _dependency(current_user: CurrentUser) -> User:
        if current_user.role not in allowed:
            raise APIHTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires one of roles: {', '.join(sorted(allowed))}",
                error_code=error_code,
            )
        return current_user

    return _dependency


def require_permission(
    permission_name: str,
    *,
    resource_type: Optional[str] = None,
    resource_id: Optional[int] = None,
    allow_roles: Optional[FrozenSet[str]] = STAFF_ROLES,
    error_code: str = "PERMISSION_DENIED",
) -> Callable[..., User]:
    """
    Gate a route on catalog / grant permission.

    Order: staff role bypass → role_permissions → group_permissions →
    user_permissions direct grant.
    """

    def _dependency(
        current_user: CurrentUser,
        db: Session = Depends(get_db),
    ) -> User:
        if allow_roles and current_user.role in allow_roles:
            return current_user

        from services.permissions import UserPermissionService

        result = UserPermissionService.check_permission(
            db=db,
            user_id=current_user.id,
            permission_name=permission_name,
            resource_type=resource_type,
            resource_id=resource_id,
        )
        if not result.get("success") or not result.get("has_permission"):
            raise APIHTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing permission: {permission_name}",
                error_code=error_code,
            )
        return current_user

    return _dependency


def require_staff(current_user: CurrentUser) -> User:
    """Allow admin, organization_admin, and super_admin only."""
    if current_user.role not in STAFF_ROLES:
        raise APIHTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Staff privileges required",
            error_code="STAFF_REQUIRED",
        )
    return current_user


StaffUser = Annotated[User, Depends(require_staff)]
SuperAdminUser = Annotated[User, Depends(require_roles("super_admin"))]
AdminUser = Annotated[
    User, Depends(require_roles("admin", error_code="DASHBOARD_ROLE_REQUIRED"))
]
OrgAdminUser = Annotated[
    User,
    Depends(require_roles("organization_admin", error_code="DASHBOARD_ROLE_REQUIRED")),
]
DashboardSuperAdminUser = Annotated[
    User,
    Depends(require_roles("super_admin", error_code="DASHBOARD_ROLE_REQUIRED")),
]
