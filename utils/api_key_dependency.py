"""Authenticate requests via JWT bearer token or X-API-Key header."""

from __future__ import annotations

from typing import Optional

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from models.user_model import User
from services.auth import AuthService
from services.permissions import ApiKeyService
from services.users import UserService
from utils.database import get_db

_bearer = HTTPBearer(auto_error=False)
API_KEY_HEADER = "X-API-Key"


def resolve_authenticated_user(
    db: Session,
    credentials: Optional[HTTPAuthorizationCredentials],
    api_key: Optional[str],
    *,
    required_permission: Optional[str] = None,
) -> User:
    """Resolve the acting user from JWT (preferred) or API key."""
    if credentials and credentials.credentials:
        user = AuthService.get_current_user(db, credentials.credentials)
        if user:
            return user

    if api_key:
        validation = ApiKeyService.validate_api_key(
            db, api_key, required_permission=required_permission
        )
        if not validation.get("success"):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=validation.get("error", "Invalid API key"),
            )
        if required_permission and not validation.get("has_permission"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"API key missing required permission: {required_permission}",
            )
        user = UserService.get_user_by_id(db, validation["user_id"])
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="API key owner not found",
            )
        return user

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_authenticated_user(
    db: Session = Depends(get_db),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
    api_key: Optional[str] = Header(None, alias=API_KEY_HEADER),
) -> User:
    return resolve_authenticated_user(db, credentials, api_key)
