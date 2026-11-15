"""Organization memberships: which organizations a user belongs to, and their role in each.

Clients pick the organization a request acts in with the ``X-Organization-Id`` header
(default: the user's home org). Adding/removing members is done from inside the
organization (header = that org) or by a platform role.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel, EmailStr, model_validator
from sqlalchemy.orm import Session

from dependencies.auth import CurrentUser, require_permission
from models.identity import OrganizationMembership
from models.user_model import Organization, User
from services.audit import AuditLogService
from services.permissions.role_catalog import (
    DEFAULT_ROLE_NAME,
    highest,
    invalidate_cache,  # noqa: F401  (re-export for admin tooling)
    is_platform_role,
)
from services.users.membership import ORG_HEADER, list_memberships
from services.users.role_policy import RoleHierarchyValidator
from services.users.role_scope import can_edit_user
from utils.api_errors import APIHTTPException
from utils.database import get_db
from utils.rate_limit_dependency import RateLimitDependency

router = APIRouter(prefix="/api/v1", tags=["Organization memberships"])


class AddMemberRequest(BaseModel):
    user_id: Optional[int] = None
    email: Optional[EmailStr] = None
    role: str = DEFAULT_ROLE_NAME

    @model_validator(mode="after")
    def _one_identifier(self):
        if (self.user_id is None) == (self.email is None):
            raise ValueError("Provide exactly one of user_id or email")
        return self


def _require_acting_in(current_user: User, organization_id: int) -> None:
    """Membership changes happen from inside the org, unless you are platform staff."""
    if is_platform_role(current_user.role):
        return
    if current_user.organization_id != organization_id:
        raise APIHTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Act in this organization first (send {ORG_HEADER}: {organization_id})",
            error_code="WRONG_ACTIVE_ORGANIZATION",
        )


def _audit(db: Session, request: Request, actor: User, action: str, org_id: int, values: dict) -> None:
    AuditLogService.log_user_action(
        db=db,
        user_id=actor.id,
        action=action,
        resource_type="organization_membership",
        resource_id=org_id,
        new_values=values,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )


@router.get("/me/organizations")
def my_organizations(current_user: CurrentUser) -> Dict[str, Any]:
    """Organizations I belong to, my role in each, and which one this request acts in."""
    return {
        "active_organization_id": current_user.organization_id,
        "organizations": list_memberships(current_user),
    }


@router.post("/organizations/{organization_id}/members", status_code=status.HTTP_201_CREATED)
def add_member(
    organization_id: int,
    body: AddMemberRequest,
    request: Request,
    current_user: User = Depends(require_permission("users:create")),
    db: Session = Depends(get_db),
    _: None = Depends(RateLimitDependency.check_rate_limit("admin_create_user")),
) -> Dict[str, Any]:
    """Add an existing user to this organization with a role in it."""
    _require_acting_in(current_user, organization_id)
    if db.query(Organization.id).filter(Organization.id == organization_id).first() is None:
        raise APIHTTPException(status_code=404, detail="Organization not found", error_code="NOT_FOUND")
    if is_platform_role(body.role) or not RoleHierarchyValidator.can_create_role(
        current_user.role, body.role
    ):
        raise APIHTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"You cannot grant role '{body.role}'",
            error_code="ROLE_NOT_ASSIGNABLE",
        )

    q = db.query(User).filter(User.deleted_at.is_(None))
    target = (
        q.filter(User.id == body.user_id).first()
        if body.user_id is not None
        else q.filter(User.email == str(body.email).lower()).first()
    )
    if target is None:
        raise APIHTTPException(
            status_code=404,
            detail="User not found (use invitations for new people)",
            error_code="NOT_FOUND",
        )
    if organization_id in target.member_org_ids():
        raise APIHTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User is already a member of this organization",
            error_code="ALREADY_MEMBER",
        )

    # Role scoped to this org; the flush hook also creates the membership.
    target.role = body.role
    target.__dict__["_pending_role_org"] = organization_id
    target.__dict__["_pending_granted_by"] = current_user.id
    db.flush()
    _audit(db, request, current_user, "membership_add", organization_id,
           {"user_id": target.id, "role": body.role})
    db.commit()
    return {"organization_id": organization_id, "user_id": target.id, "role": body.role}


@router.delete("/organizations/{organization_id}/members/{user_id}")
def remove_member(
    organization_id: int,
    user_id: int,
    request: Request,
    current_user: User = Depends(require_permission("users:update")),
    db: Session = Depends(get_db),
    _: None = Depends(RateLimitDependency.check_rate_limit("admin_create_user")),
) -> Dict[str, Any]:
    """Remove a user from this organization (their roles in it go too)."""
    _require_acting_in(current_user, organization_id)
    if user_id == current_user.id:
        raise APIHTTPException(status_code=400, detail="You cannot remove yourself", error_code="BAD_REQUEST")
    target = db.query(User).filter(User.id == user_id, User.deleted_at.is_(None)).first()
    if target is None or organization_id not in target.member_org_ids():
        raise APIHTTPException(status_code=404, detail="Membership not found", error_code="NOT_FOUND")
    if target.organization_id == organization_id:
        raise APIHTTPException(
            status_code=400,
            detail="This is the user's home organization; change their home organization first",
            error_code="HOME_ORGANIZATION",
        )
    target_role_here = highest(target.roles_in(organization_id)) or DEFAULT_ROLE_NAME
    if not can_edit_user(current_user.role, target_role_here):
        raise APIHTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You cannot manage this user",
            error_code="FORBIDDEN",
        )

    for m in list(target.memberships):
        if m.organization_id == organization_id:
            target.memberships.remove(m)
    for a in list(target.role_assignments):
        if a.organization_id == organization_id:
            target.role_assignments.remove(a)
    _audit(db, request, current_user, "membership_remove", organization_id, {"user_id": target.id})
    db.commit()
    return {"organization_id": organization_id, "user_id": user_id, "removed": True}
