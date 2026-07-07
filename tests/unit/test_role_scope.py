"""Unit tests for role visibility rules."""

import sys
from pathlib import Path
import unittest

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from services.users.role_scope import can_edit_user, can_view_user, viewable_roles_for


class TestRoleScope(unittest.TestCase):
    def test_super_admin_can_view_everyone(self):
        self.assertTrue(can_view_user("super_admin", "super_admin"))
        self.assertTrue(can_view_user("super_admin", "organization_admin"))
        self.assertTrue(can_view_user("super_admin", "user"))

    def test_org_admin_cannot_view_super_admin(self):
        self.assertFalse(can_view_user("organization_admin", "super_admin"))
        self.assertTrue(can_view_user("organization_admin", "admin"))
        self.assertTrue(can_view_user("organization_admin", "user"))

    def test_admin_only_views_users(self):
        self.assertFalse(can_view_user("admin", "organization_admin"))
        self.assertFalse(can_view_user("admin", "admin"))
        self.assertTrue(can_view_user("admin", "user"))

    def test_viewable_roles_for_admin(self):
        self.assertEqual(viewable_roles_for("admin"), ["user"])

    def test_viewable_roles_for_super_admin(self):
        self.assertIsNone(viewable_roles_for("super_admin"))

    def test_can_edit_user_hierarchy(self):
        self.assertFalse(can_edit_user("user", "user"))
        self.assertTrue(can_edit_user("super_admin", "organization_admin"))
        self.assertTrue(can_edit_user("organization_admin", "admin"))
        self.assertTrue(can_edit_user("organization_admin", "user"))
        self.assertFalse(can_edit_user("organization_admin", "organization_admin"))
        self.assertTrue(can_edit_user("admin", "user"))
        self.assertFalse(can_edit_user("admin", "admin"))


if __name__ == "__main__":
    unittest.main()
