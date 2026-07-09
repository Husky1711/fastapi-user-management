#!/usr/bin/env python3
"""Run smoke tests (pytest-free in CI for reliability)."""

from __future__ import annotations

import os
import sys
import traceback

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

if os.getenv("GITHUB_ACTIONS"):
    os.environ.setdefault("RATE_LIMIT__ENABLE_IP_LIMITS", "false")
    os.environ.setdefault("RATE_LIMIT__ENABLE_USER_LIMITS", "false")
    os.environ.setdefault("AUTH_COOKIE__USE_HTTPONLY_REFRESH", "false")
    os.environ.setdefault("AUTH_COOKIE__LEGACY_JSON_REFRESH", "true")


def _load_cross_org_ids() -> dict[str, int]:
    from models.user_model import ApiKey, User, UserGroup
    from utils.database import SessionLocal

    db = SessionLocal()
    try:
        org2_user = (
            db.query(User).filter(User.username == "testuser_org2").one_or_none()
        )
        assert org2_user is not None, "Seed user testuser_org2 missing"

        group = (
            db.query(UserGroup)
            .filter(UserGroup.name == "CI Org2 Group", UserGroup.organization_id == 2)
            .one_or_none()
        )
        assert group is not None, "Seed group CI Org2 Group missing"

        api_key = (
            db.query(ApiKey)
            .filter(ApiKey.key_name == "CI Org2 API Key", ApiKey.organization_id == 2)
            .one_or_none()
        )
        assert api_key is not None, "Seed API key CI Org2 API Key missing"

        return {
            "org2_user_id": org2_user.id,
            "org2_group_id": group.id,
            "org2_api_key_id": api_key.id,
        }
    finally:
        db.close()


def _cases(cross_org_ids: dict[str, int]) -> list[tuple[str, object, dict]]:
    from tests.smoke import test_auth_smoke, test_idor_smoke, test_rbac_smoke

    return [
        ("test_login_refresh_logout", test_auth_smoke.test_login_refresh_logout, {}),
        ("test_alembic_head_matches_schema", test_auth_smoke.test_alembic_head_matches_schema, {}),
        (
            "test_cannot_read_user_in_other_org[testorgadmin]",
            test_idor_smoke.test_cannot_read_user_in_other_org,
            {"username": "testorgadmin", "password": "orgadmin123", "cross_org_ids": cross_org_ids},
        ),
        (
            "test_cannot_read_user_in_other_org[testadmin]",
            test_idor_smoke.test_cannot_read_user_in_other_org,
            {"username": "testadmin", "password": "admin123", "cross_org_ids": cross_org_ids},
        ),
        (
            "test_cannot_access_other_org_compliance_resources[orgadmin-get-group]",
            test_idor_smoke.test_cannot_access_other_org_compliance_resources,
            {
                "username": "testorgadmin",
                "password": "orgadmin123",
                "method": "GET",
                "path_key": "org2_group_id",
                "cross_org_ids": cross_org_ids,
            },
        ),
        (
            "test_cannot_access_other_org_compliance_resources[admin-patch-group]",
            test_idor_smoke.test_cannot_access_other_org_compliance_resources,
            {
                "username": "testadmin",
                "password": "admin123",
                "method": "PATCH",
                "path_key": "org2_group_id",
                "cross_org_ids": cross_org_ids,
            },
        ),
        (
            "test_cannot_access_other_org_compliance_resources[orgadmin-get-api-key]",
            test_idor_smoke.test_cannot_access_other_org_compliance_resources,
            {
                "username": "testorgadmin",
                "password": "orgadmin123",
                "method": "GET",
                "path_key": "org2_api_key_id",
                "cross_org_ids": cross_org_ids,
            },
        ),
        (
            "test_cannot_access_other_org_compliance_resources[admin-delete-api-key]",
            test_idor_smoke.test_cannot_access_other_org_compliance_resources,
            {
                "username": "testadmin",
                "password": "admin123",
                "method": "DELETE",
                "path_key": "org2_api_key_id",
                "cross_org_ids": cross_org_ids,
            },
        ),
        (
            "test_dashboard_role_matrix[testadmin-admin-overview]",
            test_rbac_smoke.test_dashboard_role_matrix,
            {
                "username": "testadmin",
                "password": "admin123",
                "path": "/api/v1/dashboard/admin/overview",
                "expected_status": 200,
            },
        ),
        (
            "test_dashboard_role_matrix[testorgadmin-org-overview]",
            test_rbac_smoke.test_dashboard_role_matrix,
            {
                "username": "testorgadmin",
                "password": "orgadmin123",
                "path": "/api/v1/dashboard/organization-admin/overview",
                "expected_status": 200,
            },
        ),
        (
            "test_dashboard_role_matrix[test_super_admin-super-overview]",
            test_rbac_smoke.test_dashboard_role_matrix,
            {
                "username": "test_super_admin",
                "password": "TestSuperAdminPass123!",
                "path": "/api/v1/dashboard/super-admin/overview",
                "expected_status": 200,
            },
        ),
        (
            "test_dashboard_role_matrix[testuser-user-overview]",
            test_rbac_smoke.test_dashboard_role_matrix,
            {
                "username": "testuser",
                "password": "user123",
                "path": "/api/v1/dashboard/user/overview",
                "expected_status": 200,
            },
        ),
        (
            "test_dashboard_role_matrix[testorgadmin-denied-admin]",
            test_rbac_smoke.test_dashboard_role_matrix,
            {
                "username": "testorgadmin",
                "password": "orgadmin123",
                "path": "/api/v1/dashboard/admin/overview",
                "expected_status": 403,
            },
        ),
        (
            "test_dashboard_role_matrix[testuser-denied-admin]",
            test_rbac_smoke.test_dashboard_role_matrix,
            {
                "username": "testuser",
                "password": "user123",
                "path": "/api/v1/dashboard/admin/overview",
                "expected_status": 403,
            },
        ),
        (
            "test_dashboard_role_matrix[testadmin-denied-super]",
            test_rbac_smoke.test_dashboard_role_matrix,
            {
                "username": "testadmin",
                "password": "admin123",
                "path": "/api/v1/dashboard/super-admin/overview",
                "expected_status": 403,
            },
        ),
        ("test_user_cannot_create_users", test_rbac_smoke.test_user_cannot_create_users, {}),
    ]


def main() -> int:
    from config.settings import settings
    from fastapi.testclient import TestClient

    from main import app

    print(
        "smoke settings:",
        f"ip_limits={settings.rate_limit.enable_ip_limits}",
        f"httponly={settings.auth_cookie.use_httponly_refresh}",
        f"db={settings.get_database_url()}",
    )

    cross_org_ids = _load_cross_org_ids()
    cases = _cases(cross_org_ids)
    print(f"running {len(cases)} smoke cases")
    failures: list[str] = []

    for label, func, kwargs in cases:
        try:
            with TestClient(app) as client:
                func(client, **kwargs)
            print("PASS", label)
        except Exception as exc:
            print("FAIL", label, exc)
            traceback.print_exc()
            failures.append(label)

    print(f"summary: {len(cases) - len(failures)} passed, {len(failures)} failed")
    for label in failures:
        print("FAILED:", label)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
