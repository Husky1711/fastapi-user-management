"""Unit-scoped access: roles granted on an org unit cover that unit and its subtree.

The only place that answers "does a role held on a unit cover this person/unit?".
Org-wide checks never consult unit grants (see ``rbac_catalog_service``), so a
department head is a plain user org-wide and an admin only within their department.

A grant covers a target when the unit's ``path`` is a prefix of the target unit's path.
It must also *grant the permission* (``role_permissions``) and, for actions on
people, outrank the target's org role (normal hierarchy, via ``role_scope``).
"""

from __future__ import annotations

from typing import Dict, List, Optional

from sqlalchemy import exists, or_
from sqlalchemy.orm import Session

from models.identity import User
from models.rbac_model import Permission, Role, RolePermission, UserRole
from models.units import OrgUnit, OrgUnitMember
from services.permissions.role_catalog import highest


def unit_grants(db: Session, user: User, permission: str) -> List[Dict[str, object]]:
    """Unit-scoped roles ``user`` holds in the active org that grant ``permission``.

    Returns ``[{"unit_id", "path", "role", "scope"}]``; scope ``own`` means the grant
    reaches only people the holder is related to (services/permissions/relations).
    """
    org_id = user.organization_id  # active org for this request
    rows = (
        db.query(OrgUnit.id, OrgUnit.path, Role.name, RolePermission.scope)
        .join(UserRole, UserRole.unit_id == OrgUnit.id)
        .join(Role, Role.id == UserRole.role_id)
        .join(RolePermission, RolePermission.role_id == Role.id)
        .join(Permission, Permission.id == RolePermission.permission_id)
        .filter(
            UserRole.user_id == user.id,
            OrgUnit.organization_id == org_id,
            Permission.name == permission,
        )
        .all()
    )
    return [
        {"unit_id": uid, "path": path, "role": role, "scope": scope or "all"}
        for uid, path, role, scope in rows
    ]


def unit_paths_of(db: Session, user_id: int, organization_id: int) -> List[str]:
    return [
        p
        for (p,) in db.query(OrgUnit.path)
        .join(OrgUnitMember, OrgUnitMember.unit_id == OrgUnit.id)
        .filter(OrgUnitMember.user_id == user_id, OrgUnit.organization_id == organization_id)
        .all()
    ]


def role_over_user(db: Session, actor: User, target: User, permission: str) -> Optional[str]:
    """Highest unit role of ``actor`` covering any unit ``target`` is placed in.

    ``own``-scoped grants only count when the actor is related to the target.
    """
    from services.permissions.relations import is_related

    grants = unit_grants(db, actor, permission)
    if not grants:
        return None
    target_paths = unit_paths_of(db, target.id, actor.organization_id)
    covering = [g for g in grants if any(tp.startswith(g["path"]) for tp in target_paths)]
    if any(g["scope"] == "own" for g in covering) and not is_related(
        db, actor.id, actor.organization_id, target.id
    ):
        covering = [g for g in covering if g["scope"] != "own"]
    return highest(g["role"] for g in covering)


def role_over_unit(db: Session, actor: User, unit: OrgUnit, permission: str) -> Optional[str]:
    """Highest unit role of ``actor`` on ``unit`` or one of its ancestors."""
    return highest(
        g["role"] for g in unit_grants(db, actor, permission) if unit.path.startswith(g["path"])
    )


def in_subtrees(paths: List[str], organization_id: int):
    """SQL condition: ``User`` is placed in a unit under any of ``paths``."""
    return exists().where(
        OrgUnitMember.user_id == User.id,
        OrgUnitMember.unit_id == OrgUnit.id,
        OrgUnit.organization_id == organization_id,
        or_(*[OrgUnit.path.startswith(p) for p in paths]),
    )


def has_any_unit_grant(db: Session, user: User, permission: str) -> bool:
    return bool(unit_grants(db, user, permission))
