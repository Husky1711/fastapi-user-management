"""Relations between people (teacher teaches student, doctor attends patient...).

They drive ``own``-scoped permissions: a role holding ``users:read@own`` reaches only
people it is related to. All endpoints act in the active organization.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from dependencies.auth import CurrentUser
from models.relations import ResourceRelation
from models.user_model import User
from services.audit import AuditLogService
from services.permissions.relations import (
    OBJECT_USER,
    list_relations,
    permission_scope,
    serialize,
)
from services.permissions.role_catalog import is_manager_role, is_platform_role
from services.permissions.unit_access import role_over_user, unit_grants, unit_paths_of
from services.sector.template_service import TemplateError, validate_relation
from services.users.role_scope import can_edit_user, can_view_user
from utils.api_errors import APIHTTPException
from utils.database import get_db

router = APIRouter(prefix="/api/v1", tags=["Relations"])


class CreateRelationRequest(BaseModel):
    subject_user_id: int = Field(..., description="Who holds the relation (e.g. the teacher)")
    relation: str = Field(..., min_length=1, max_length=50, description="e.g. teaches, attends")
    object_user_id: int = Field(..., description="Who it points to (e.g. the student)")


def _forbidden(detail: str = "Missing permission: users:update"):
    raise APIHTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail, error_code="PERMISSION_DENIED")


def _member(db: Session, user_id: int, org_id: int) -> User:
    user = db.query(User).filter(User.id == user_id, User.deleted_at.is_(None)).first()
    if user is None or org_id not in user.member_org_ids():
        raise APIHTTPException(status_code=404, detail="User not found in this organization", error_code="NOT_FOUND")
    return user


def _acting_role_over(db: Session, actor: User, *people: User) -> str:
    """Role allowed to link these people: full-scope users:update org-wide, or a
    full-scope unit role covering all of them."""
    if is_platform_role(actor.role) or permission_scope(db, actor, "users:update") == "all":
        return actor.role
    grants = [g for g in unit_grants(db, actor, "users:update") if g["scope"] == "all"]
    roles = []
    for person in people:
        paths = unit_paths_of(db, person.id, actor.organization_id)
        covering = [g["role"] for g in grants if any(p.startswith(g["path"]) for p in paths)]
        if not covering:
            _forbidden()
        roles.append(covering)
    # a single unit role must cover everyone
    common = set(roles[0]).intersection(*roles[1:]) if roles else set()
    if not common:
        _forbidden()
    from services.permissions.role_catalog import highest

    return highest(common)


@router.get("/relations")
def get_relations(
    current_user: CurrentUser,
    subject_user_id: Optional[int] = None,
    object_user_id: Optional[int] = None,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Relations in the active org.

    Non-managers may only list their own. Managers see a relation only when they can
    see both people in it (so relations between people above them stay hidden).
    """
    if not is_manager_role(current_user.role) and subject_user_id != current_user.id:
        _forbidden("You can only list your own relations (subject_user_id=<your id>)")
    rows = list_relations(db, current_user.organization_id, subject_user_id, object_user_id)
    if not is_platform_role(current_user.role):
        visible: Dict[int, bool] = {}

        def can_see(user_id: int) -> bool:
            if user_id not in visible:
                visible[user_id] = _can_see(db, current_user, user_id)
            return visible[user_id]

        rows = [r for r in rows if can_see(r.subject_user_id) and can_see(r.object_id)]
    return {"relations": [serialize(r) for r in rows]}


def _can_see(db: Session, actor: User, user_id: int) -> bool:
    """Actor is the person, outranks them org-wide, or covers them via a unit role."""
    if user_id == actor.id:
        return True
    person = db.query(User).filter(User.id == user_id, User.deleted_at.is_(None)).first()
    if person is None or actor.organization_id not in person.member_org_ids():
        return False
    if can_view_user(actor.role, person.role):
        return True
    unit_role = role_over_user(db, actor, person, "users:read")
    return unit_role is not None and can_view_user(unit_role, person.role)


@router.post("/relations", status_code=status.HTTP_201_CREATED)
def create_relation(
    body: CreateRelationRequest,
    request: Request,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    org_id = current_user.organization_id
    if body.subject_user_id == body.object_user_id:
        raise APIHTTPException(status_code=400, detail="A person cannot be related to themselves", error_code="BAD_REQUEST")
    relation = body.relation.strip().lower()
    try:
        validate_relation(org_id, relation)
    except TemplateError as exc:
        raise APIHTTPException(status_code=exc.status, detail=str(exc), error_code="BAD_REQUEST")
    subject = _member(db, body.subject_user_id, org_id)
    obj = _member(db, body.object_user_id, org_id)
    acting = _acting_role_over(db, current_user, subject, obj)
    if not is_platform_role(acting) and not (
        can_edit_user(acting, subject.role) and can_edit_user(acting, obj.role)
    ):
        _forbidden("You must outrank both people to link them")
    existing = (
        db.query(ResourceRelation)
        .filter(
            ResourceRelation.organization_id == org_id,
            ResourceRelation.subject_user_id == subject.id,
            ResourceRelation.relation == relation,
            ResourceRelation.object_type == OBJECT_USER,
            ResourceRelation.object_id == obj.id,
        )
        .first()
    )
    if existing:
        raise APIHTTPException(status_code=409, detail="Relation already exists", error_code="CONFLICT")
    row = ResourceRelation(
        organization_id=org_id, subject_user_id=subject.id, relation=relation,
        object_type=OBJECT_USER, object_id=obj.id, created_by=current_user.id,
    )
    db.add(row)
    db.flush()
    AuditLogService.log_user_action(
        db=db, user_id=current_user.id, action="relation_create", resource_type="relation",
        resource_id=row.id, new_values=serialize(row),
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    db.commit()
    return serialize(row)


@router.delete("/relations/{relation_id}")
def delete_relation(
    relation_id: int,
    request: Request,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    org_id = current_user.organization_id
    row = (
        db.query(ResourceRelation)
        .filter(ResourceRelation.id == relation_id, ResourceRelation.organization_id == org_id)
        .first()
    )
    if row is None:
        raise APIHTTPException(status_code=404, detail="Relation not found", error_code="NOT_FOUND")
    subject = _member(db, row.subject_user_id, org_id)
    obj = _member(db, row.object_id, org_id)
    acting = _acting_role_over(db, current_user, subject, obj)
    if not is_platform_role(acting) and not (
        can_edit_user(acting, subject.role) and can_edit_user(acting, obj.role)
    ):
        _forbidden("You must outrank both people to unlink them")
    data = serialize(row)
    db.delete(row)
    AuditLogService.log_user_action(
        db=db, user_id=current_user.id, action="relation_delete", resource_type="relation",
        resource_id=relation_id, old_values=data,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    db.commit()
    return {"id": relation_id, "deleted": True}
