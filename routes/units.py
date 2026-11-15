"""Organization units (departments, classes, wards, sites...) and roles on them.

All endpoints act in the request's active organization (``X-Organization-Id``).
A role granted on a unit covers that unit and its subtree, never the whole org.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from dependencies.auth import CurrentUser, require_permission
from models.user_model import User
from services.audit import AuditLogService
from services.permissions.role_catalog import is_platform_role
from services.permissions.unit_access import role_over_unit
from services.permissions.user_permission_service import UserPermissionService
from services.users.role_policy import RoleHierarchyValidator
from services.users.role_scope import can_edit_user
from services.users.unit_service import UnitError, UnitService
from utils.api_errors import APIHTTPException
from utils.database import get_db
from utils.rate_limit_dependency import RateLimitDependency

router = APIRouter(prefix="/api/v1", tags=["Organization units"])


class CreateUnitRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=150)
    unit_type: str = Field(..., min_length=1, max_length=50, description="e.g. department, class, ward")
    parent_id: Optional[int] = None


class UpdateUnitRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=150)
    unit_type: Optional[str] = Field(None, min_length=1, max_length=50)


class UnitMemberRequest(BaseModel):
    user_id: int


class UnitRoleRequest(BaseModel):
    user_id: int
    role: str = Field(..., min_length=1, max_length=50)


def _fail(exc: UnitError):
    raise APIHTTPException(status_code=exc.status, detail=str(exc), error_code=_CODES.get(exc.status, "BAD_REQUEST"))


_CODES = {400: "BAD_REQUEST", 403: "FORBIDDEN", 404: "NOT_FOUND", 409: "CONFLICT"}


def _org_permission(db: Session, actor: User, permission: str) -> bool:
    result = UserPermissionService.check_permission(db=db, user_id=actor.id, permission_name=permission)
    return bool(result.get("success") and result.get("has_permission"))


def _acting_role_over_unit(db: Session, actor: User, unit, permission: str) -> tuple[str, bool]:
    """``(role, via_unit)``: org-wide role if it has the permission, else a covering unit role."""
    if _org_permission(db, actor, permission):
        return actor.role, False
    unit_role = role_over_unit(db, actor, unit, permission)
    if unit_role is None:
        raise APIHTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Missing permission: {permission}",
            error_code="PERMISSION_DENIED",
        )
    return unit_role, True


def _get_target(db: Session, user_id: int) -> User:
    user = db.query(User).filter(User.id == user_id, User.deleted_at.is_(None)).first()
    if user is None:
        raise APIHTTPException(status_code=404, detail="User not found", error_code="NOT_FOUND")
    return user


def _audit(db: Session, request: Request, actor: User, action: str, unit_id: int, values: dict) -> None:
    AuditLogService.log_user_action(
        db=db,
        user_id=actor.id,
        action=action,
        resource_type="org_unit",
        resource_id=unit_id,
        new_values=values,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )


# --- tree ---------------------------------------------------------------------

@router.get("/units")
def list_units(current_user: CurrentUser, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """The active organization's unit tree (ordered so parents precede children)."""
    return {
        "organization_id": current_user.organization_id,
        "units": UnitService.list_tree(db, current_user.organization_id),
    }


@router.post("/units", status_code=status.HTTP_201_CREATED)
def create_unit(
    body: CreateUnitRequest,
    request: Request,
    current_user: User = Depends(require_permission("organizations:update")),
    db: Session = Depends(get_db),
    _: None = Depends(RateLimitDependency.check_rate_limit("admin_create_user")),
) -> Dict[str, Any]:
    try:
        unit = UnitService.create_unit(
            db, current_user.organization_id, body.name, body.unit_type, body.parent_id
        )
    except UnitError as exc:
        _fail(exc)
    _audit(db, request, current_user, "unit_create", unit.id, UnitService.serialize(unit))
    db.commit()
    return UnitService.serialize(unit)


@router.patch("/units/{unit_id}")
def update_unit(
    unit_id: int,
    body: UpdateUnitRequest,
    request: Request,
    current_user: User = Depends(require_permission("organizations:update")),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    try:
        unit = UnitService.get_unit(db, current_user.organization_id, unit_id)
        UnitService.update_unit(db, unit, body.name, body.unit_type)
    except UnitError as exc:
        _fail(exc)
    _audit(db, request, current_user, "unit_update", unit.id, body.model_dump(exclude_none=True))
    db.commit()
    return UnitService.serialize(unit)


@router.delete("/units/{unit_id}")
def delete_unit(
    unit_id: int,
    request: Request,
    current_user: User = Depends(require_permission("organizations:update")),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    try:
        unit = UnitService.get_unit(db, current_user.organization_id, unit_id)
        UnitService.delete_unit(db, unit)
    except UnitError as exc:
        _fail(exc)
    _audit(db, request, current_user, "unit_delete", unit_id, {})
    db.commit()
    return {"id": unit_id, "deleted": True}


# --- people in units -------------------------------------------------------------

@router.get("/units/{unit_id}/members")
def list_unit_members(
    unit_id: int,
    current_user: CurrentUser,
    include_subtree: bool = False,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    try:
        unit = UnitService.get_unit(db, current_user.organization_id, unit_id)
    except UnitError as exc:
        _fail(exc)
    _acting_role_over_unit(db, current_user, unit, "users:list")  # raises if not allowed
    people = UnitService.members(db, unit, include_subtree=include_subtree)
    return {
        "unit": UnitService.serialize(unit),
        "members": [
            {"id": u.id, "username": u.username, "email": u.email, "role": u.role} for u in people
        ],
    }


@router.post("/units/{unit_id}/members", status_code=status.HTTP_201_CREATED)
def add_unit_member(
    unit_id: int,
    body: UnitMemberRequest,
    request: Request,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    try:
        unit = UnitService.get_unit(db, current_user.organization_id, unit_id)
        acting, via_unit = _acting_role_over_unit(db, current_user, unit, "users:update")
        target = _get_target(db, body.user_id)
        if via_unit and not can_edit_user(acting, target.role):
            raise UnitError("You cannot place this user", 403)
        added = UnitService.add_member(db, unit, target)
    except UnitError as exc:
        _fail(exc)
    _audit(db, request, current_user, "unit_member_add", unit.id, {"user_id": target.id})
    db.commit()
    return {"unit_id": unit.id, "user_id": target.id, "added": added}


@router.delete("/units/{unit_id}/members/{user_id}")
def remove_unit_member(
    unit_id: int,
    user_id: int,
    request: Request,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    try:
        unit = UnitService.get_unit(db, current_user.organization_id, unit_id)
        acting, via_unit = _acting_role_over_unit(db, current_user, unit, "users:update")
        target = _get_target(db, user_id)
        if via_unit and not can_edit_user(acting, target.role):
            raise UnitError("You cannot manage this user", 403)
        UnitService.remove_member(db, unit, target)
    except UnitError as exc:
        _fail(exc)
    _audit(db, request, current_user, "unit_member_remove", unit.id, {"user_id": user_id})
    db.commit()
    return {"unit_id": unit_id, "user_id": user_id, "removed": True}


# --- roles on units --------------------------------------------------------------

@router.get("/units/{unit_id}/roles")
def list_unit_roles(unit_id: int, current_user: CurrentUser, db: Session = Depends(get_db)) -> Dict[str, Any]:
    try:
        unit = UnitService.get_unit(db, current_user.organization_id, unit_id)
    except UnitError as exc:
        _fail(exc)
    _acting_role_over_unit(db, current_user, unit, "users:list")
    return {"unit": UnitService.serialize(unit), "roles": UnitService.role_grants(db, unit)}


@router.post("/units/{unit_id}/roles", status_code=status.HTTP_201_CREATED)
def grant_unit_role(
    unit_id: int,
    body: UnitRoleRequest,
    request: Request,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Grant a role on this unit (applies to the unit and everything below it)."""
    try:
        unit = UnitService.get_unit(db, current_user.organization_id, unit_id)
        acting, _via_unit = _acting_role_over_unit(db, current_user, unit, "users:update")
        if is_platform_role(body.role) or not RoleHierarchyValidator.can_create_role(acting, body.role):
            raise UnitError(f"You cannot grant role '{body.role}'", 403)
        target = _get_target(db, body.user_id)
        if target.id == current_user.id:
            raise UnitError("You cannot grant roles to yourself", 403)
        granted = UnitService.grant_role(db, unit, target, body.role, granted_by=current_user.id)
    except UnitError as exc:
        _fail(exc)
    except ValueError as exc:  # unknown role name
        _fail(UnitError(str(exc), 400))
    _audit(db, request, current_user, "unit_role_grant", unit.id, {"user_id": target.id, "role": body.role})
    db.commit()
    return {"unit_id": unit.id, "user_id": target.id, "role": body.role, "granted": granted}


@router.delete("/units/{unit_id}/roles/{user_id}/{role}")
def revoke_unit_role(
    unit_id: int,
    user_id: int,
    role: str,
    request: Request,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    try:
        unit = UnitService.get_unit(db, current_user.organization_id, unit_id)
        acting, _via_unit = _acting_role_over_unit(db, current_user, unit, "users:update")
        if not RoleHierarchyValidator.can_create_role(acting, role):
            raise UnitError(f"You cannot revoke role '{role}'", 403)
        target = _get_target(db, user_id)
        UnitService.revoke_role(db, unit, target, role)
    except UnitError as exc:
        _fail(exc)
    _audit(db, request, current_user, "unit_role_revoke", unit.id, {"user_id": user_id, "role": role})
    db.commit()
    return {"unit_id": unit_id, "user_id": user_id, "role": role, "revoked": True}
