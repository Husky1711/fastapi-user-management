"""
Role policy — hierarchy, creation rights, and shared RBAC helpers.

Assignment rule (data-driven, see services/permissions/role_catalog.py): a user may
grant only system roles with a strictly lower ``level`` than their own. Adding a
role (e.g. ``teacher``) is a row in ``roles``, not a code change.
"""

from __future__ import annotations

from typing import List

from services.permissions.role_catalog import assignable_roles, role_info


class RoleHierarchyValidator:
    """Utility class for role hierarchy validation."""

    @classmethod
    def can_create_role(cls, creator_role: str, target_role: str) -> bool:
        return target_role in assignable_roles(creator_role)

    @classmethod
    def get_allowed_roles(cls, creator_role: str) -> List[str]:
        return assignable_roles(creator_role)

    @classmethod
    def is_valid_role(cls, role: str) -> bool:
        return role_info(role) is not None


def assert_not_self_admin_edit(editor_id: int, target_id: int) -> None:
    """Block admins from using admin endpoints against themselves."""
    if editor_id == target_id:
        raise ValueError("Cannot perform this admin action on your own account")
