"""Unit tests for shared auth dependencies."""

import sys
from pathlib import Path
import unittest
from unittest.mock import MagicMock

from fastapi import HTTPException

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from dependencies.auth import STAFF_ROLES, require_roles, require_staff


def _user(role: str) -> MagicMock:
    user = MagicMock()
    user.role = role
    user.id = 1
    return user


class TestRequireRoles(unittest.TestCase):
    def test_allows_matching_role(self):
        dep = require_roles("admin", "super_admin")
        user = _user("admin")
        self.assertIs(dep(user), user)

    def test_denies_non_matching_role(self):
        dep = require_roles("super_admin")
        with self.assertRaises(HTTPException) as ctx:
            dep(_user("admin"))
        self.assertEqual(ctx.exception.status_code, 403)

    def test_super_admin_only(self):
        dep = require_roles("super_admin")
        user = _user("super_admin")
        self.assertIs(dep(user), user)


class TestRequireStaff(unittest.TestCase):
    def test_staff_roles_allowed(self):
        for role in STAFF_ROLES:
            with self.subTest(role=role):
                self.assertIs(require_staff(_user(role)), _user(role))

    def test_regular_user_denied(self):
        with self.assertRaises(HTTPException) as ctx:
            require_staff(_user("user"))
        self.assertEqual(ctx.exception.status_code, 403)


if __name__ == "__main__":
    unittest.main()
