"""
Schema constraint integration tests — unique indexes / org isolation guards.

Covers DB §8 / readiness 10.9 for constraints introduced in Alembic uniques migration.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.exc import IntegrityError

from models.user_model import Organization, UserGroup
from utils.database import SessionLocal

pytestmark = pytest.mark.integration


def _suffix() -> str:
    return uuid.uuid4().hex[:10]


@pytest.mark.integration
def test_organizations_slug_unique():
    db = SessionLocal()
    slug = f"constraint-test-{_suffix()}"
    try:
        a = Organization(name=f"Org A {_suffix()}", slug=slug, status="active")
        db.add(a)
        db.commit()

        b = Organization(name=f"Org B {_suffix()}", slug=slug, status="active")
        db.add(b)
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
    finally:
        db.query(Organization).filter(Organization.slug == slug).delete(
            synchronize_session=False
        )
        db.commit()
        db.close()


@pytest.mark.integration
def test_user_groups_unique_name_per_org():
    db = SessionLocal()
    name = f"constraint-group-{_suffix()}"
    try:
        from models.user_model import User

        creator = db.query(User).filter_by(username="testadmin").one()
        g1 = UserGroup(
            name=name,
            organization_id=1,
            created_by=creator.id,
            description="constraint test",
        )
        db.add(g1)
        db.commit()

        g2 = UserGroup(
            name=name,
            organization_id=1,
            created_by=creator.id,
            description="duplicate",
        )
        db.add(g2)
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
    finally:
        db.query(UserGroup).filter(UserGroup.name == name).delete(
            synchronize_session=False
        )
        db.commit()
        db.close()


@pytest.mark.integration
def test_user_groups_same_name_different_orgs_allowed():
    db = SessionLocal()
    name = f"shared-name-{_suffix()}"
    try:
        from models.user_model import User

        creator = db.query(User).filter_by(username="testadmin").one()
        g1 = UserGroup(
            name=name,
            organization_id=1,
            created_by=creator.id,
            description="org1",
        )
        g2 = UserGroup(
            name=name,
            organization_id=2,
            created_by=creator.id,
            description="org2",
        )
        db.add_all([g1, g2])
        db.commit()
        assert g1.id != g2.id
    finally:
        db.query(UserGroup).filter(UserGroup.name == name).delete(
            synchronize_session=False
        )
        db.commit()
        db.close()


@pytest.mark.integration
def test_user_permissions_organization_id_populated_on_grant():
    from services.permissions.user_permission_service import UserPermissionService
    from models.user_model import User, UserPermission

    db = SessionLocal()
    perm_name = f"constraint:test:{_suffix()}"
    try:
        user = db.query(User).filter_by(username="testuser").one()
        result = UserPermissionService.grant_permission(
            db,
            user_id=user.id,
            permission_name=perm_name,
            granted_by=user.id,
        )
        assert result["success"] is True, result
        row = (
            db.query(UserPermission)
            .filter(
                UserPermission.user_id == user.id,
                UserPermission.permission_name == perm_name,
            )
            .one()
        )
        assert row.organization_id == user.organization_id
    finally:
        db.query(UserPermission).filter(UserPermission.permission_name == perm_name).delete(
            synchronize_session=False
        )
        db.commit()
        db.close()
