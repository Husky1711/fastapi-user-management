"""Sector templates and organization vocabulary (UI wording)."""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from dependencies.auth import CurrentUser, require_permission
from models.units import OrgUnit
from models.user_model import Organization, User
from services.audit import AuditLogService
from services.permissions.role_catalog import is_platform_role
from services.permissions.user_permission_service import UserPermissionService
from services.sector.template_service import (
    TemplateError,
    apply_template,
    get_template,
    list_templates,
    roles_blocking_switch,
    vocabulary,
)
from utils.api_errors import APIHTTPException
from utils.database import get_db

router = APIRouter(prefix="/api/v1", tags=["Sector templates"])


class ApplyTemplateRequest(BaseModel):
    template: str = Field(..., min_length=1, max_length=50)


class VocabularyPatch(BaseModel):
    terms: Optional[Dict[str, Optional[str]]] = None
    role_labels: Optional[Dict[str, Optional[str]]] = None


def _fail(exc: TemplateError):
    raise APIHTTPException(
        status_code=exc.status,
        detail=str(exc),
        error_code={404: "NOT_FOUND", 409: "CONFLICT"}.get(exc.status, "BAD_REQUEST"),
    )


def _org(db: Session, org_id: int) -> Organization:
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if org is None:
        raise APIHTTPException(status_code=404, detail="Organization not found", error_code="NOT_FOUND")
    return org


@router.get("/sector-templates")
def get_sector_templates(_: CurrentUser) -> Dict[str, Any]:
    """Available sector templates (education, medical, pharma, ...)."""
    return {"templates": list_templates()}


@router.get("/vocabulary")
def get_vocabulary(current_user: CurrentUser, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """UI wording for the active organization (terms, role labels, unit types)."""
    return vocabulary(_org(db, current_user.organization_id))


@router.patch("/vocabulary")
def patch_vocabulary(
    body: VocabularyPatch,
    request: Request,
    current_user: User = Depends(require_permission("organizations:update")),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Override words for the active organization (null removes an override)."""
    org = _org(db, current_user.organization_id)
    overrides = dict(org.vocabulary_overrides or {})
    for section, changes in (("terms", body.terms), ("role_labels", body.role_labels)):
        if changes is None:
            continue
        current = dict(overrides.get(section) or {})
        for key, value in changes.items():
            if value is None or not str(value).strip():
                current.pop(key, None)
            else:
                current[key] = str(value).strip()[:100]
        overrides[section] = current
    org.vocabulary_overrides = overrides
    AuditLogService.log_user_action(
        db=db, user_id=current_user.id, action="vocabulary_update", resource_type="organization",
        resource_id=org.id, new_values=body.model_dump(exclude_none=True),
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    db.commit()
    return vocabulary(org)


@router.put("/organizations/{organization_id}/sector-template")
def set_sector_template(
    organization_id: int,
    body: ApplyTemplateRequest,
    request: Request,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Choose an organization's sector template and create its roles.

    Platform staff for any org; org admins (organizations:update) for the org they act in.
    Refused if existing units do not fit the new template's unit types.
    """
    if not is_platform_role(current_user.role):
        allowed = current_user.organization_id == organization_id and UserPermissionService.check_permission(
            db=db, user_id=current_user.id, permission_name="organizations:update"
        ).get("has_permission")
        if not allowed:
            raise APIHTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Missing permission: organizations:update",
                error_code="PERMISSION_DENIED",
            )
    org = _org(db, organization_id)
    try:
        template = get_template(body.template)
        specs = {u["key"]: u for u in template["unit_types"]}
        units = {u.id: u for u in db.query(OrgUnit).filter(OrgUnit.organization_id == org.id)}
        misfits = []
        for u in units.values():
            parent_type = units[u.parent_id].unit_type if u.parent_id else None
            spec = specs.get(u.unit_type)
            if spec is None or parent_type not in spec.get("parents", [None]):
                misfits.append(f"{u.name} ({u.unit_type})")
        if misfits:
            raise TemplateError(
                "Existing units do not fit this template: " + ", ".join(sorted(misfits)[:10]), 409
            )
        blocking = roles_blocking_switch(db, org.id, body.template)
        if blocking:
            held = ", ".join(f"{role} ({n})" for role, n in sorted(blocking.items()))
            raise TemplateError(
                f"People still hold roles this template does not use: {held}. "
                "Change or revoke those roles first.",
                409,
            )
        result = apply_template(db, org, body.template)
    except TemplateError as exc:
        _fail(exc)
    AuditLogService.log_user_action(
        db=db, user_id=current_user.id, action="sector_template_apply", resource_type="organization",
        resource_id=org.id, new_values={"template": body.template},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    db.commit()
    return {**result, "vocabulary": vocabulary(org)}
