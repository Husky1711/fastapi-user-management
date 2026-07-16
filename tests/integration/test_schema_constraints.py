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
    # Must be a catalog permission (FK on permission_id).
    perm_name = "analytics:view"
    resource_type = f"constraint-{_suffix()}"
    try:
        user = db.query(User).filter_by(username="testuser").one()
        result = UserPermissionService.grant_permission(
            db,
            user_id=user.id,
            permission_name=perm_name,
            resource_type=resource_type,
            resource_id=0,
            granted_by=user.id,
        )
        assert result["success"] is True, result
        row = (
            db.query(UserPermission)
            .filter(
                UserPermission.user_id == user.id,
                UserPermission.permission_name == perm_name,
                UserPermission.resource_type == resource_type,
            )
            .one()
        )
        assert row.organization_id == user.organization_id
        assert row.permission_id is not None
    finally:
        db.query(UserPermission).filter(
            UserPermission.permission_name == perm_name,
            UserPermission.resource_type == resource_type,
        ).delete(synchronize_session=False)
        db.commit()
        db.close()


@pytest.mark.integration
def test_pending_invite_unique_per_org_email():
    from models.user_model import User, UserInvitation
    from utils.datetime_utc import utc_now
    from datetime import timedelta

    db = SessionLocal()
    email = f"pending-unique-{_suffix()}@example.com"
    try:
        inviter = db.query(User).filter_by(username="testadmin").one()
        expires = utc_now() + timedelta(days=3)
        a = UserInvitation(
            organization_id=1,
            email=email,
            role="user",
            token_hash=f"tok-a-{_suffix()}",
            invited_by=inviter.id,
            expires_at=expires,
        )
        db.add(a)
        db.commit()

        b = UserInvitation(
            organization_id=1,
            email=email,
            role="admin",
            token_hash=f"tok-b-{_suffix()}",
            invited_by=inviter.id,
            expires_at=expires,
        )
        db.add(b)
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
    finally:
        db.query(UserInvitation).filter(UserInvitation.email == email).delete(
            synchronize_session=False
        )
        db.commit()
        db.close()


@pytest.mark.integration
def test_soft_deleted_user_email_username_reusable():
    """Active-only unique indexes free email/username after soft-delete."""
    from models.user_model import User
    from services.users.user_service import UserService
    from utils.jwt_config import get_password_hash
    from utils.datetime_utc import utc_now

    db = SessionLocal()
    suffix = _suffix()
    username = f"reuse-u-{suffix}"
    email = f"reuse-{suffix}@example.com"
    created_ids: list[int] = []
    try:
        editor = db.query(User).filter_by(username="test_super_admin").one()
        first = User(
            username=username,
            email=email,
            password_hash=get_password_hash("TempPass123!"),
            status="active",
            role="user",
            organization_id=1,
            phone_number="1234567890",
        )
        db.add(first)
        db.commit()
        db.refresh(first)
        created_ids.append(first.id)

        result = UserService.soft_delete_user(db, editor, first.id)
        assert result["success"] is True, result

        # Same email/username must be insertable for a new active user
        second = User(
            username=username,
            email=email,
            password_hash=get_password_hash("TempPass123!"),
            status="active",
            role="user",
            organization_id=1,
            phone_number="1234567890",
        )
        db.add(second)
        db.commit()
        db.refresh(second)
        created_ids.append(second.id)
        assert second.id != first.id
        assert second.deleted_at is None

        # Two active users with same email must still fail
        third = User(
            username=f"{username}-x",
            email=email,
            password_hash=get_password_hash("TempPass123!"),
            status="active",
            role="user",
            organization_id=1,
            phone_number="1234567890",
        )
        db.add(third)
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
    finally:
        for uid in created_ids:
            db.query(User).filter(User.id == uid).delete(synchronize_session=False)
        db.commit()
        db.close()


@pytest.mark.integration
def test_users_email_column_is_255():
    from sqlalchemy import text

    db = SessionLocal()
    try:
        row = db.execute(
            text(
                """
                SELECT CHARACTER_MAXIMUM_LENGTH
                FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA = DATABASE()
                  AND TABLE_NAME = 'users'
                  AND COLUMN_NAME = 'email'
                """
            )
        ).one()
        assert int(row[0]) >= 255
    finally:
        db.close()


@pytest.mark.integration
def test_seeded_users_have_no_role_drift():
    from services.permissions.rbac_catalog_service import RbacCatalogService

    db = SessionLocal()
    try:
        drifts = RbacCatalogService.find_role_drifts(db)
        seed_names = {
            "testadmin",
            "testuser",
            "testorgadmin",
            "testuser_org2",
            "test_super_admin",
        }
        seed_drifts = [d for d in drifts if d.get("username") in seed_names]
        assert seed_drifts == [], seed_drifts
    finally:
        db.close()
