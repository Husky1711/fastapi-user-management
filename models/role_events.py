"""Persist role assignments and memberships just before each flush.

``User.role`` is a property; its setter records the requested system role. This hook
makes ``user_roles`` / ``organization_memberships`` match:

* **Tenant roles** (``is_platform`` false) are scoped to one organization — the
  request's active org when the user is a member of it, else the user's home org —
  and replace the user's other system roles in that org (and any platform role).
* **Platform roles** are unscoped and replace all of the user's system roles.
* New users get ``DEFAULT_ROLE_NAME`` and a membership in their home org; a tenant
  role in an org implies membership there.
* Changing a user's home org (``users.organization_id``) moves the old org's
  membership and roles to the new org — today's single-org behaviour.

Default system roles missing from ``roles`` (fresh/test databases) are created from
``DEFAULT_SYSTEM_ROLES``; any other unknown name raises instead of being stored.
"""

from __future__ import annotations

from sqlalchemy import event, inspect
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


def _ensure_membership(user, org_id) -> None:
    from models.identity import OrganizationMembership

    if org_id is None:
        return
    for m in user.memberships:
        if m.organization_id == org_id:
            if m.status != "active":
                m.status = "active"
            return
    user.memberships.append(OrganizationMembership(organization_id=org_id, status="active"))


def _move_home_org(user, old_org, new_org) -> None:
    """Home org changed: move membership + roles scoped to the old org."""
    old_m = next((m for m in user.memberships if m.organization_id == old_org), None)
    has_new = any(m.organization_id == new_org for m in user.memberships)
    if old_m is not None:
        if has_new:
            user.memberships.remove(old_m)
        else:
            old_m.organization_id = new_org
    new_role_ids = {a.role_id for a in user.role_assignments if a.organization_id == new_org}
    for a in list(user.role_assignments):
        if a.organization_id == old_org:
            if a.role_id in new_role_ids:
                user.role_assignments.remove(a)
            else:
                a.organization_id = new_org
                a.scope_key = new_org


def _is_system(r) -> bool:
    return r is not None and r.is_system and r.org_scope_key == 0


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
            is_new = user in session.new
            if not is_new:
                hist = inspect(user).attrs.organization_id.history
                if hist.has_changes() and hist.deleted and hist.added:
                    _move_home_org(user, hist.deleted[0], hist.added[0])
            if is_new:
                _ensure_membership(user, user.organization_id)

            pending = user.__dict__.get("_pending_system_role")
            if pending is None and is_new and not user.role_assignments:
                pending = DEFAULT_ROLE_NAME
            if pending is None:
                continue

            role = _system_role(session, pending)
            if role.is_platform:
                scope_org = None
            else:
                scope_org = user.__dict__.get("_pending_role_org") or user.role_context_org_id()
                _ensure_membership(user, scope_org)

            for assignment in list(user.role_assignments):
                r = assignment.role
                if not _is_system(r) or r is role and assignment.organization_id == scope_org:
                    continue
                same_scope = assignment.organization_id == scope_org
                if role.is_platform or same_scope or assignment.organization_id is None:
                    user.role_assignments.remove(assignment)  # delete-orphan
            if not any(
                a.role is role and a.organization_id == scope_org for a in user.role_assignments
            ):
                user.role_assignments.append(
                    UserRole(
                        role=role,
                        organization_id=scope_org,
                        scope_key=scope_org or 0,
                        granted_by=user.__dict__.get("_pending_granted_by"),
                        granted_at=utc_now(),
                    )
                )
            for key in ("_pending_system_role", "_pending_granted_by", "_pending_role_org"):
                user.__dict__.pop(key, None)
