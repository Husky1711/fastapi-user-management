"""Backward-compatible aggregator for production feature routers.

Prefer importing focused modules (`routes.groups`, `routes.api_keys`, etc.).
"""

from fastapi import APIRouter

from routes.sessions_admin import router as sessions_admin_router
from routes.permissions_mgmt import router as permissions_router
from routes.groups import router as groups_router
from routes.api_keys import router as api_keys_router
from routes.password_history import router as password_history_router

router = APIRouter()
router.include_router(sessions_admin_router)
router.include_router(permissions_router)
router.include_router(groups_router)
router.include_router(api_keys_router)
router.include_router(password_history_router)

__all__ = ["router"]
