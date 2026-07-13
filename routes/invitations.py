"""Admin invitation endpoints."""

from typing import Any, Dict, Optional

from fastapi import Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy.orm import Session

from config.settings import settings
from dependencies.auth import STAFF_ROLES, require_permission
from models.user_model import User
from routes.auth_common import create_api_router
from services.users.invitation_service import InvitationService
from utils.database import get_db
from utils.rate_limit_dependency import RateLimitDependency

router = create_api_router(tags=["Invitations"])


class CreateInvitationRequest(BaseModel):
    email: EmailStr
    role: str = Field(default="user")
    organization_id: Optional[int] = None
    expires_in_days: int = Field(default=7, ge=1, le=30)


class AcceptInvitationRequest(BaseModel):
    token: str = Field(..., min_length=20, max_length=128)
    username: str = Field(..., min_length=3, max_length=30)
    password: str = Field(..., min_length=8, max_length=100)

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        policy = settings.password_policy
        if len(v) < policy.min_password_length:
            raise ValueError(
                f"Password must be at least {policy.min_password_length} characters"
            )
        if policy.require_uppercase and not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if policy.require_lowercase and not any(c.islower() for c in v):
            raise ValueError("Password must contain at least one lowercase letter")
        if policy.require_digits and not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        if policy.require_special_chars and not any(
            c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in v
        ):
            raise ValueError("Password must contain at least one special character")
        return v


@router.post("/invitations")
async def create_invitation(
    body: CreateInvitationRequest,
    current_user: User = Depends(require_permission("users:create")),
    db: Session = Depends(get_db),
    _: None = Depends(RateLimitDependency.check_rate_limit("admin_create_user")),
) -> Dict[str, Any]:
    if current_user.role not in STAFF_ROLES:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Staff only")
    result = InvitationService.create_invitation(
        db,
        inviter=current_user,
        email=str(body.email),
        role=body.role,
        organization_id=body.organization_id,
        expires_in_days=body.expires_in_days,
    )
    if not result["success"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=result["error"])
    return result


@router.get("/invitations")
async def list_invitations(
    current_user: User = Depends(require_permission("users:list")),
    db: Session = Depends(get_db),
    include_accepted: bool = False,
    _: None = Depends(RateLimitDependency.check_rate_limit("users_list")),
) -> Dict[str, Any]:
    if current_user.role not in STAFF_ROLES:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Staff only")
    return InvitationService.list_invitations(
        db, current_user, include_accepted=include_accepted
    )


@router.get("/invitations/validate/{token}")
async def validate_invitation(
    token: str,
    db: Session = Depends(get_db),
    _: None = Depends(RateLimitDependency.check_rate_limit("signup", require_auth=False)),
) -> Dict[str, Any]:
    result = InvitationService.validate_token(db, token)
    if not result.get("valid"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=result.get("error"))
    return result


@router.post("/invitations/accept")
async def accept_invitation(
    body: AcceptInvitationRequest,
    db: Session = Depends(get_db),
    _: None = Depends(RateLimitDependency.check_rate_limit("signup", require_auth=False)),
) -> Dict[str, Any]:
    result = InvitationService.accept_invitation(
        db, body.token, body.username, body.password
    )
    if not result["success"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=result["error"])
    return result


@router.delete("/invitations/{invitation_id}")
async def revoke_invitation(
    invitation_id: int,
    current_user: User = Depends(require_permission("users:create")),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    if current_user.role not in STAFF_ROLES:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Staff only")
    result = InvitationService.revoke_invitation(db, current_user, invitation_id)
    if not result["success"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=result["error"])
    return result
