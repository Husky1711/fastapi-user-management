"""Role rules are data: hierarchy behaviour comes from level/is_platform/can_view_peers.

The key property for reuse: a product can add a role (here ``teacher``) as data and
every rule — visibility, editing, assignment, manager eligibility — follows.
"""

from types import SimpleNamespace

import pytest

from services.permissions import role_catalog as rc
from services.permissions.rbac_catalog_service import RbacCatalogService
from services.users.role_policy import RoleHierarchyValidator
from services.users.role_scope import can_edit_user, can_view_user, viewable_roles_for


def test_default_hierarchy_unchanged():
    assert RoleHierarchyValidator.get_allowed_roles("super_admin") == [
        "organization_admin", "admin", "user"
    ]
    assert RoleHierarchyValidator.get_allowed_roles("organization_admin") == ["admin", "user"]
    assert RoleHierarchyValidator.get_allowed_roles("admin") == ["user"]
    assert RoleHierarchyValidator.get_allowed_roles("user") == []
    assert viewable_roles_for("organization_admin") == ["organization_admin", "admin", "user"]
    assert rc.is_platform_role("super_admin") and not rc.is_platform_role("admin")
    assert rc.is_base_role("user") and not rc.is_manager_role("user")
    assert all(rc.is_manager_role(r) for r in ("admin", "organization_admin", "super_admin"))


def test_unknown_role_has_no_powers():
    assert not RoleHierarchyValidator.is_valid_role("hacker")
    assert viewable_roles_for("hacker") == []
    assert not can_edit_user("hacker", "user")
    assert not rc.is_manager_role("hacker")


@pytest.fixture
def college_roles(monkeypatch):
    roles = {r.name: r for r in rc.DEFAULT_SYSTEM_ROLES}
    roles["teacher"] = rc.RoleInfo("teacher", 15, description="Teacher")
    monkeypatch.setattr(rc, "_load_from_db", lambda: roles)
    rc.invalidate_cache()
    yield
    rc.invalidate_cache()


def test_new_role_needs_no_code(college_roles):
    # teacher (15) sits between user (10) and admin (20)
    assert viewable_roles_for("teacher") == ["user"]
    assert can_edit_user("teacher", "user")
    assert not can_view_user("teacher", "admin")
    assert RoleHierarchyValidator.get_allowed_roles("teacher") == ["user"]
    assert rc.is_manager_role("teacher")
    # higher roles automatically see and manage the new role
    assert "teacher" in viewable_roles_for("admin")
    assert RoleHierarchyValidator.can_create_role("admin", "teacher")
    assert can_edit_user("organization_admin", "teacher")
    assert can_view_user("super_admin", "teacher")
    # and the new role cannot reach above itself
    assert not RoleHierarchyValidator.can_create_role("teacher", "admin")


def test_apply_effective_role_is_derived():
    user = SimpleNamespace(id=7, role="admin")
    assert RbacCatalogService.apply_effective_role(None, user) == "admin"


def test_highest_picks_top_level():
    assert rc.highest(["user", "organization_admin", "admin"]) == "organization_admin"
    assert rc.highest([]) is None


@pytest.fixture
def platform_staff(monkeypatch):
    roles = {r.name: r for r in rc.DEFAULT_SYSTEM_ROLES}
    roles["platform_admin"] = rc.RoleInfo("platform_admin", 90, is_platform=True)
    monkeypatch.setattr(rc, "_load_from_db", lambda: roles)
    rc.invalidate_cache()
    yield
    rc.invalidate_cache()


def test_platform_admins_respect_levels(platform_staff):
    # super admin can create and manage a lower platform admin
    assert RoleHierarchyValidator.can_create_role("super_admin", "platform_admin")
    assert can_edit_user("super_admin", "platform_admin")
    # a platform admin manages every tenant role ...
    assert can_edit_user("platform_admin", "organization_admin")
    assert can_view_user("platform_admin", "super_admin")
    # ... but not the super admin, a peer, or itself-level roles
    assert not can_edit_user("platform_admin", "super_admin")
    assert not can_edit_user("platform_admin", "platform_admin")
    assert not RoleHierarchyValidator.can_create_role("platform_admin", "super_admin")
    # and super admins no longer edit each other
    assert not can_edit_user("super_admin", "super_admin")
