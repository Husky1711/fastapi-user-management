"""
Role policy — hierarchy, creation rights, and shared RBAC helpers.

Single place for role assignment rules (previously duplicated in schemas).
"""

from __future__ import annotations

from typing import List


VALID_ROLES = frozenset({"user", "admin", "organization_admin", "super_admin"})

# Who may assign which roles when creating/updating users.
ROLE_HIERARCHY: dict[str, List[str]] = {
    "super_admin": ["organization_admin", "admin", "user"],
    "organization_admin": ["admin", "user"],
    "admin": ["user"],
    "user": [],
}


class RoleHierarchyValidator:
    """Utility class for role hierarchy validation."""

    ROLE_HIERARCHY = ROLE_HIERARCHY

    @classmethod
    def can_create_role(cls, creator_role: str, target_role: str) -> bool:
        allowed_roles = cls.ROLE_HIERARCHY.get(creator_role, [])
        return target_role in allowed_roles

    @classmethod
    def get_allowed_roles(cls, creator_role: str) -> List[str]:
        return list(cls.ROLE_HIERARCHY.get(creator_role, []))

    @classmethod
    def is_valid_role(cls, role: str) -> bool:
        return role in VALID_ROLES


def assert_not_self_admin_edit(editor_id: int, target_id: int) -> None:
    """Block admins from using admin endpoints against themselves."""
    if editor_id == target_id:
        raise ValueError("Cannot perform this admin action on your own account")
