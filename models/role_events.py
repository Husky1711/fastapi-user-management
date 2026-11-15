"""Persist ``user.role = name`` into ``user_roles`` (the only place roles are stored).

``User.role`` is a property; its setter records the requested system role. Just
before each flush this hook makes ``user_roles`` match it:
  * other *system* role assignments are removed (org-scoped custom roles untouched),
  * the requested role is assigned if missing,
  * new users with no role get ``DEFAULT_ROLE_NAME``.
Default system roles missing from ``roles`` (fresh/test databases) are created from
``DEFAULT_SYSTEM_ROLES``; any other unknown name raises instead of being stored.
"""

from __future__ import annotations

from sqlalchemy import event
from sqlalchemy.orm import Session


def _system_role(session: Session, name: str):
    from models.rbac_model import Role
    from services.permissions.role_catalog import DEFAULT_SYSTEM_ROLES, invalidate_cache

    role = (
        session.query(Role)
        .filter(Role.name == name, Role.is_system.is_(True), Role.org_scope_key == 0)
        .one_or_none()
    )
    if role is not None:
        return role
    default = next((r for r in DEFAULT_SYSTEM_ROLES if r.name == name), None)
    if default is None:
        raise ValueError(f"Unknown system role '{name}' (add it to the roles table first)")
    role = Role(
        name=default.name,
        organization_id=None,
        org_scope_key=0,
        is_system=True,
        level=default.level,
        is_platform=default.is_platform,
        can_view_peers=default.can_view_peers,
        description=default.description,
    )
    session.add(role)
    invalidate_cache()
    return role


@event.listens_for(Session, "before_flush")
def _apply_pending_system_roles(session: Session, flush_context, instances) -> None:
    from models.identity import User
    from models.rbac_model import UserRole
    from services.permissions.role_catalog import DEFAULT_ROLE_NAME
    from utils.datetime_utc import utc_now

    seen: set[int] = set()
    users = [
        obj
        for obj in (*session.new, *session.identity_map.values())
        if isinstance(obj, User) and not (id(obj) in seen or seen.add(id(obj)))
    ]
    with session.no_autoflush:
        for user in users:
            pending = user.__dict__.get("_pending_system_role")
            if pending is None and user in session.new and not user.role_assignments:
                pending = DEFAULT_ROLE_NAME
            if pending is None:
                continue
            role = _system_role(session, pending)
            for assignment in list(user.role_assignments):
                r = assignment.role
                if r is not None and r.is_system and r.org_scope_key == 0 and r is not role:
                    user.role_assignments.remove(assignment)  # delete-orphan
            if not any(a.role is role for a in user.role_assignments):
                user.role_assignments.append(
                    UserRole(
                        role=role,
                        granted_by=user.__dict__.get("_pending_granted_by"),
                        granted_at=utc_now(),
                    )
                )
            user.__dict__.pop("_pending_system_role", None)
            user.__dict__.pop("_pending_granted_by", None)
