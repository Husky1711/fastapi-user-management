"""Shared authentication and role dependencies."""

from __future__ import annotations

from typing import Annotated, Callable, FrozenSet

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from models.user_model import User
from services.auth import AuthService
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
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_roles(*roles: str) -> Callable[..., User]:
    """Factory: dependency that allows only the given roles."""
    allowed = frozenset(roles)

    def _dependency(current_user: CurrentUser) -> User:
        if current_user.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return current_user

    return _dependency


def require_staff(current_user: CurrentUser) -> User:
    """Allow admin, organization_admin, and super_admin only."""
    if current_user.role not in STAFF_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Staff privileges required",
        )
    return current_user


StaffUser = Annotated[User, Depends(require_staff)]
SuperAdminUser = Annotated[User, Depends(require_roles("super_admin"))]
