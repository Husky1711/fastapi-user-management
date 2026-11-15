"""Unit tests for shared auth dependencies."""

import sys
from pathlib import Path
import unittest
from unittest.mock import MagicMock

from fastapi import HTTPException

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from dependencies.auth import require_platform, require_roles, require_staff


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


class TestRequireStaff(unittest.TestCase):
    def test_roles_above_base_allowed(self):
        for role in ("admin", "organization_admin", "super_admin"):
            with self.subTest(role=role):
                user = _user(role)
                self.assertIs(require_staff(user), user)

    def test_regular_user_denied(self):
        with self.assertRaises(HTTPException) as ctx:
            require_staff(_user("user"))
        self.assertEqual(ctx.exception.status_code, 403)


class TestRequirePlatform(unittest.TestCase):
    def test_platform_role_allowed(self):
        user = _user("super_admin")
        self.assertIs(require_platform()(user), user)

    def test_tenant_roles_denied(self):
        for role in ("user", "admin", "organization_admin"):
            with self.subTest(role=role):
                with self.assertRaises(HTTPException) as ctx:
                    require_platform()(_user(role))
                self.assertEqual(ctx.exception.status_code, 403)


if __name__ == "__main__":
    unittest.main()
