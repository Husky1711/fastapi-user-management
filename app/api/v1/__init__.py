"""Version 1 of the public API.

Feature routers are listed in `FEATURE_ROUTERS` (from roadmap step 3 on). Every route under
`/api/v1` documents the standard error responses (422, 500) in the problem-details format,
and every successful answer is sent with `Cache-Control: no-store`.
"""

from fastapi import APIRouter, Depends

from app.api.v1 import auth, me
from app.core.deps import no_store
from app.schemas.errors import API_ERROR_RESPONSES

FEATURE_ROUTERS: tuple[APIRouter, ...] = (auth.router, me.router)


def build_api_router(*extra_routers: APIRouter) -> APIRouter:
    """The `/api/v1` router with every feature router (plus `extra_routers`, used by tests)."""
    api_router = APIRouter(
        prefix="/api/v1", responses=API_ERROR_RESPONSES, dependencies=[Depends(no_store)]
    )
    for router in (*FEATURE_ROUTERS, *extra_routers):
        api_router.include_router(router)
    return api_router
