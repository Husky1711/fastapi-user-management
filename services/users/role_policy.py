"""
Role policy — hierarchy, creation rights, and shared RBAC helpers.

Assignment rule (data-driven, see services/permissions/role_catalog.py): a user may
grant only system roles with a strictly lower ``level`` than their own. Adding a
role (e.g. ``teacher``) is a row in ``roles``, not a code change.
"""

from __future__ import annotations

from typing import List, Optional

from services.permissions.role_catalog import assignable_roles, role_info


class RoleHierarchyValidator:
    """Utility class for role hierarchy validation.

    With ``organization_id``, roles are also limited to those the organization's
    sector template uses (default roles + template roles), so e.g. a hospital role
    cannot be granted in a college.
    """

    @classmethod
    def can_create_role(
        cls, creator_role: str, target_role: str, organization_id: Optional[int] = None
    ) -> bool:
        return target_role in cls.get_allowed_roles(creator_role, organization_id)

    @classmethod
    def get_allowed_roles(
        cls, creator_role: str, organization_id: Optional[int] = None
    ) -> List[str]:
        roles = assignable_roles(creator_role)
        if organization_id is None:
            return roles
        from services.sector.template_service import allowed_role_names

        allowed = allowed_role_names(organization_id)
        return roles if allowed is None else [r for r in roles if r in allowed]

    @classmethod
    def is_valid_role(cls, role: str) -> bool:
        return role_info(role) is not None


def assert_not_self_admin_edit(editor_id: int, target_id: int) -> None:
    """Block admins from using admin endpoints against themselves."""
    if editor_id == target_id:
        raise ValueError("Cannot perform this admin action on your own account")
