"""Role-based visibility rules for org-scoped user listings."""

from __future__ import annotations

from typing import List, Optional

from sqlalchemy.orm import Query

from models.user_model import User

# System-wide roles never appear in organization-scoped views.
ORG_INVISIBLE_ROLES = frozenset({"super_admin"})

# Roles each viewer may see within their organization (None = all except invisible).
_VIEWABLE_ROLES: dict[str, Optional[List[str]]] = {
    "organization_admin": ["organization_admin", "admin", "user"],
    "admin": ["user"],
}

_ROLE_RANK: dict[str, int] = {
    "user": 1,
    "admin": 2,
    "organization_admin": 3,
    "super_admin": 4,
}

_MANAGER_ROLES = frozenset({"admin", "organization_admin", "super_admin"})


def viewable_roles_for(viewer_role: str) -> Optional[List[str]]:
    if viewer_role == "super_admin":
        return None
    return _VIEWABLE_ROLES.get(viewer_role, [])


def can_view_user(viewer_role: str, target_role: str) -> bool:
    if viewer_role == "super_admin":
        return True
    if target_role in ORG_INVISIBLE_ROLES:
        return False
    allowed = viewable_roles_for(viewer_role)
    if allowed is None:
        return True
    return target_role in allowed


def can_edit_user(editor_role: str, target_role: str) -> bool:
    """Editors may change users they can view who are strictly below them in rank."""
    if editor_role == "user":
        return False
    if not can_view_user(editor_role, target_role):
        return False
    if editor_role == "super_admin":
        return True
    return _ROLE_RANK.get(target_role, 0) < _ROLE_RANK.get(editor_role, 0)


def is_manager_role(role: str) -> bool:
    return role in _MANAGER_ROLES


def filter_users_for_viewer(
    query: Query,
    viewer_role: str,
    org_id: Optional[int],
) -> Query:
    if viewer_role == "super_admin":
        return query

    if org_id is None:
        return query.filter(False)

    query = query.filter(User.organization_id == org_id)
    query = query.filter(User.role.notin_(list(ORG_INVISIBLE_ROLES)))

    allowed = viewable_roles_for(viewer_role)
    if allowed is not None:
        if not allowed:
            return query.filter(False)
        query = query.filter(User.role.in_(allowed))

    return query
