"""
Bootstrap MySQL for CI and local smoke tests.

Runs Alembic migrations and seeds known test users (bcrypt passwords).
"""

from __future__ import annotations

import os
import sys
import time

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from sqlalchemy import text  # noqa: E402
from sqlalchemy.exc import OperationalError  # noqa: E402

from models.user_model import Organization, User, UserGroup, ApiKey  # noqa: E402
from utils.database import SessionLocal, engine  # noqa: E402
from utils.jwt_config import get_password_hash  # noqa: E402

SEED_USERS: tuple[tuple[str, str, str, str, int], ...] = (
    ("testadmin", "admin@test.com", "admin123", "admin", 1),
    ("testuser", "user@test.com", "user123", "user", 1),
    ("testorgadmin", "orgadmin@test.com", "orgadmin123", "organization_admin", 1),
    ("testuser_org2", "user2@test.com", "user2123", "user", 2),
    ("test_super_admin", "test_super_admin@test.com", "TestSuperAdminPass123!", "super_admin", 2),
)

SEED_ORGS: tuple[tuple[int, str, str], ...] = (
    (1, "Default Organization", "CI / Codespaces development organization"),
    (2, "System", "Platform-level scope for super admins"),
)


def _wait_for_database(max_attempts: int = 30, delay_seconds: float = 2.0) -> None:
    for attempt in range(1, max_attempts + 1):
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            print("Database is reachable.")
            return
        except OperationalError as exc:
            print(f"Waiting for database ({attempt}/{max_attempts}): {exc}")
            time.sleep(delay_seconds)
    raise RuntimeError("Database did not become ready in time.")


def _run_migrations() -> None:
    from scripts.bootstrap_local_db import main as bootstrap_main

    bootstrap_main()


def _seed_data() -> None:
    db = SessionLocal()
    try:
        for org_id, name, description in SEED_ORGS:
            org = db.query(Organization).filter(Organization.id == org_id).first()
            if org is None:
                db.add(
                    Organization(
                        id=org_id,
                        name=name,
                        description=description,
                        status="active",
                    )
                )

        db.flush()

        for username, email, password, role, organization_id in SEED_USERS:
            user = db.query(User).filter(User.username == username).first()
            hashed = get_password_hash(password)
            if user is None:
                db.add(
                    User(
                        username=username,
                        email=email,
                        password=hashed,
                        status="active",
                        phone_number="1234567890",
                        role=role,
                        organization_id=organization_id,
                    )
                )
            else:
                user.email = email
                user.role = role
                user.organization_id = organization_id
                user.password = hashed
                user.status = "active"

        admin = db.query(User).filter(User.username == "testadmin").first()
        test_user = db.query(User).filter(User.username == "testuser").first()
        if admin and test_user:
            test_user.manager_id = admin.id

        super_admin = db.query(User).filter(User.username == "test_super_admin").first()
        org2_user = db.query(User).filter(User.username == "testuser_org2").first()
        if super_admin and org2_user:
            group = (
                db.query(UserGroup)
                .filter(UserGroup.name == "CI Org2 Group", UserGroup.organization_id == 2)
                .first()
            )
            if group is None:
                group = UserGroup(
                    name="CI Org2 Group",
                    description="Cross-org IDOR smoke fixture",
                    organization_id=2,
                    created_by=super_admin.id,
                    is_active=True,
                )
                db.add(group)
                db.flush()

            api_key = (
                db.query(ApiKey)
                .filter(ApiKey.key_name == "CI Org2 API Key", ApiKey.organization_id == 2)
                .first()
            )
            if api_key is None:
                from services.permissions.api_key_service import ApiKeyService

                result = ApiKeyService.create_api_key(
                    db=db,
                    user_id=org2_user.id,
                    organization_id=2,
                    key_name="CI Org2 API Key",
                    created_by=super_admin.id,
                )
                if not result.get("success"):
                    raise RuntimeError(
                        f"Failed to seed CI Org2 API Key: {result.get('error')}"
                    )

        db.commit()
        print("Seed users and organizations are ready.")
    finally:
        db.close()


def main() -> None:
    _wait_for_database()
    _run_migrations()
    _seed_data()


if __name__ == "__main__":
    main()
