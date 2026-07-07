"""
Deprecated: identity routes were split into auth, sessions, users, and profile.

Kept for backward compatibility with imports of ``routes.login.router``.
"""

from fastapi import APIRouter

from routes.auth import router as _auth_router
from routes.profile import router as _profile_router
from routes.sessions import router as _sessions_router
from routes.users import router as _users_router

router = APIRouter()
router.include_router(_auth_router)
router.include_router(_sessions_router)
router.include_router(_users_router)
router.include_router(_profile_router)

__all__ = ["router"]
