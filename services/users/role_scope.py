"""Role-based visibility rules for org-scoped user listings.

All rules come from role data (``level`` / ``is_platform`` / ``can_view_peers`` on
``roles``) via ``services.permissions.role_catalog`` — no role names here:
  * platform roles see and manage everyone; tenant users never see platform users;
  * others see strictly lower levels in their organization, plus peers when the role
    has ``can_view_peers``;
  * editing requires visibility and a strictly lower target level.
"""

from __future__ import annotations

from typing import List, Optional

from sqlalchemy import and_, or_
from sqlalchemy.orm import Query

from models.rbac_model import Role, UserRole
from models.user_model import User
from services.users.membership import member_of
from services.permissions.role_catalog import (
    is_manager_role,
    is_platform_role,
    level_of,
    visible_role_names,
)

__all__ = [
    "viewable_roles_for",
    "can_view_user",
    "can_edit_user",
    "is_manager_role",
    "filter_users_for_viewer",
]


def viewable_roles_for(viewer_role: str) -> Optional[List[str]]:
    """Role names a viewer may see in their org; None = all (platform roles)."""
    return visible_role_names(viewer_role)


def can_view_user(viewer_role: str, target_role: str) -> bool:
    allowed = viewable_roles_for(viewer_role)
    return allowed is None or target_role in allowed


def can_edit_user(editor_role: str, target_role: str) -> bool:
    """Editors may change users they can view who are strictly below them in rank.

    Applies to platform roles too: a platform admin (e.g. level 90) manages every
    tenant user but not a super admin (100) or other platform admins at its level.
    """
    if not can_view_user(editor_role, target_role):
        return False
    return level_of(target_role) < level_of(editor_role)


def filter_users_for_viewer(
    query: Query,
    viewer_role: str,
    org_id: Optional[int],
) -> Query:
    if is_platform_role(viewer_role):
        return query

    if org_id is None:
        return query.filter(False)

    allowed = viewable_roles_for(viewer_role) or []
    if not allowed:
        return query.filter(False)

    # Roles live in user_roles, scoped per org: judge each user by the system roles
    # that apply in this org (org-scoped or platform-wide).
    in_org = and_(
        or_(UserRole.organization_id == org_id, UserRole.organization_id.is_(None)),
        UserRole.unit_id.is_(None),  # org role only; unit grants never count here
    )
    has_visible_role = (
        query.session.query(UserRole.id)
        .join(Role, Role.id == UserRole.role_id)
        .filter(
            UserRole.user_id == User.id,
            Role.is_system.is_(True),
            Role.org_scope_key == 0,
            Role.name.in_(allowed),
            in_org,
        )
        .exists()
    )
    has_hidden_role = (
        query.session.query(UserRole.id)
        .join(Role, Role.id == UserRole.role_id)
        .filter(
            UserRole.user_id == User.id,
            Role.is_system.is_(True),
            Role.org_scope_key == 0,
            Role.name.notin_(allowed),
            in_org,
        )
        .exists()
    )
    return query.filter(
        member_of(org_id),
        has_visible_role,
        ~has_hidden_role,  # a higher (invisible) role anywhere hides the user
    )
