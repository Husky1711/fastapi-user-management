"""Unit tests for compliance access helpers."""

import sys
from pathlib import Path
import unittest
from unittest.mock import MagicMock

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from fastapi import HTTPException

from services.users.compliance_access import require_group_manager


class TestComplianceAccess(unittest.TestCase):
    def test_require_group_manager_allows_staff(self):
        for role in ("super_admin", "organization_admin", "admin"):
            viewer = MagicMock(role=role)
            require_group_manager(viewer)

    def test_require_group_manager_blocks_user(self):
        viewer = MagicMock(role="user")
        with self.assertRaises(HTTPException) as ctx:
            require_group_manager(viewer)
        self.assertEqual(ctx.exception.status_code, 403)


if __name__ == "__main__":
    unittest.main()
