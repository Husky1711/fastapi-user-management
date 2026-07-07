"""Integration endpoints for machine-to-machine API key authentication."""

from typing import Any, Dict

from fastapi import APIRouter, Depends

from models.user_model import User
from utils.api_key_dependency import get_authenticated_user

router = APIRouter(prefix="/api/v1/integration", tags=["Integration"])


@router.get("/whoami", response_model=Dict[str, Any])
async def integration_whoami(
    current_user: User = Depends(get_authenticated_user),
) -> Dict[str, Any]:
    """
    Return the authenticated principal (JWT or X-API-Key).

    Use this endpoint to verify API key setup for M2M integrations.
    """
    return {
        "success": True,
        "user": {
            "id": current_user.id,
            "username": current_user.username,
            "email": current_user.email,
            "role": current_user.role,
            "organization_id": current_user.organization_id,
        },
        "auth_method": "api_key_or_jwt",
    }
