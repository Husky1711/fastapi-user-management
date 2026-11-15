"""Relations between people and "own" permission scopes.

A role permission is granted with a scope (``role_permissions.scope``):
  * ``all`` — reaches anyone the role may otherwise reach (level/org/unit rules);
  * ``own`` — reaches only people the holder is related to in ``resource_relations``
    (``holder —relation→ person``), e.g. a teacher's students, a doctor's patients.

Direct and group grants, and platform roles, always count as ``all``.
Applies to user-management permissions (users:list/read/update/delete); other
resources treat ``own`` as ``all`` until they get relation-aware handlers.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy import exists, or_
from sqlalchemy.orm import Session

from models.identity import User
from models.rbac_model import Permission, Role, RolePermission, UserRole
from models.relations import ResourceRelation

OBJECT_USER = "user"


# --- scope of a permission -------------------------------------------------------

def permission_scope(db: Session, actor: User, permission: str) -> Optional[str]:
    """Org-level scope of ``permission`` for ``actor``: 'all', 'own' or None.

    Cached on the request's DB session (``db.info``), so a request that checks the
    same scope several times queries once; nothing outlives the request.
    """
    cache = db.info.setdefault("permission_scope_cache", {})
    key = (actor.id, actor.organization_id, permission)
    if key not in cache:
        cache[key] = _permission_scope(db, actor, permission)
    return cache[key]


def _permission_scope(db: Session, actor: User, permission: str) -> Optional[str]:
    from services.permissions.user_permission_service import UserPermissionService

    org = actor.organization_id
    # platform roles, direct grants, group grants => all
    platform = (
        db.query(Role.id)
        .join(UserRole, UserRole.role_id == Role.id)
        .filter(UserRole.user_id == actor.id, Role.is_platform.is_(True), UserRole.unit_id.is_(None))
        .first()
    )
    if platform is not None:
        return "all"
    scopes = {
        s
        for (s,) in db.query(RolePermission.scope)
        .join(Permission, Permission.id == RolePermission.permission_id)
        .join(UserRole, UserRole.role_id == RolePermission.role_id)
        .filter(
            UserRole.user_id == actor.id,
            UserRole.unit_id.is_(None),
            or_(UserRole.organization_id == org, UserRole.organization_id.is_(None)),
            Permission.name == permission,
        )
        .all()
    }
    if "all" in scopes:
        return "all"
    check = UserPermissionService.check_permission(db=db, user_id=actor.id, permission_name=permission)
    if check.get("has_permission") and check.get("permission_type") in ("direct", "group"):
        return "all"
    return "own" if "own" in scopes else None


def role_scope_for(db: Session, role_name: str, permission: str) -> Optional[str]:
    """Scope a given system role holds a permission with ('all'/'own'/None)."""
    role = (
        db.query(Role)
        .filter(Role.name == role_name, Role.is_system.is_(True), Role.org_scope_key == 0)
        .one_or_none()
    )
    if role is None:
        return None
    if role.is_platform:
        return "all"
    return (
        db.query(RolePermission.scope)
        .join(Permission, Permission.id == RolePermission.permission_id)
        .filter(RolePermission.role_id == role.id, Permission.name == permission)
        .scalar()
    )


# --- relations ----------------------------------------------------------------------

def related_to(actor_id: int, organization_id: int):
    """SQL condition: ``User`` is related to the actor (actor —any relation→ User)."""
    return exists().where(
        ResourceRelation.organization_id == organization_id,
        ResourceRelation.subject_user_id == actor_id,
        ResourceRelation.object_type == OBJECT_USER,
        ResourceRelation.object_id == User.id,
    )


def is_related(db: Session, actor_id: int, organization_id: int, target_id: int) -> bool:
    return (
        db.query(ResourceRelation.id)
        .filter(
            ResourceRelation.organization_id == organization_id,
            ResourceRelation.subject_user_id == actor_id,
            ResourceRelation.object_type == OBJECT_USER,
            ResourceRelation.object_id == target_id,
        )
        .first()
        is not None
    )


def serialize(r: ResourceRelation) -> Dict[str, Any]:
    return {
        "id": r.id,
        "organization_id": r.organization_id,
        "subject_user_id": r.subject_user_id,
        "relation": r.relation,
        "object_type": r.object_type,
        "object_id": r.object_id,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }


def list_relations(
    db: Session, organization_id: int, subject_user_id: Optional[int] = None, object_user_id: Optional[int] = None
) -> List[ResourceRelation]:
    q = db.query(ResourceRelation).filter(ResourceRelation.organization_id == organization_id)
    if subject_user_id is not None:
        q = q.filter(ResourceRelation.subject_user_id == subject_user_id)
    if object_user_id is not None:
        q = q.filter(ResourceRelation.object_type == OBJECT_USER, ResourceRelation.object_id == object_user_id)
    return q.order_by(ResourceRelation.id).all()
