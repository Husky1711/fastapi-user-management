#!/usr/bin/env python3
"""CI smoke test runner (auth, RBAC matrix, IDOR)."""

from __future__ import annotations

import os
import sys
from typing import Any

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

if os.getenv("GITHUB_ACTIONS"):
    os.environ.setdefault("RATE_LIMIT__ENABLE_IP_LIMITS", "false")
    os.environ.setdefault("RATE_LIMIT__ENABLE_USER_LIMITS", "false")
    os.environ.setdefault("AUTH_COOKIE__USE_HTTPONLY_REFRESH", "false")
    os.environ.setdefault("AUTH_COOKIE__LEGACY_JSON_REFRESH", "true")


def _login(client, username: str, password: str) -> dict[str, Any]:
    client.cookies.clear()
    response = client.post(
        "/api/v1/login",
        json={"username": username, "password": password},
    )
    if response.status_code != 200:
        raise AssertionError(f"login failed for {username}: {response.status_code} {response.text}")
    return response.json()


def _auth_headers(access_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token}"}


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


def _run_auth_smoke(client) -> None:
    tokens = _login(client, "testuser", "user123")
    assert tokens.get("access_token")
    assert tokens.get("refresh_token")

    profile = client.get("/api/v1/profile", headers=_auth_headers(tokens["access_token"]))
    assert profile.status_code == 200, profile.text
    assert profile.json()["username"] == "testuser"

    client.cookies.clear()
    refresh = client.post(
        "/api/v1/refresh",
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert refresh.status_code == 200, refresh.text
    refreshed = refresh.json()
    assert refreshed.get("access_token")
    rotated = refreshed.get("refresh_token")
    assert rotated, f"refresh body missing token: {refreshed}"

    client.cookies.clear()
    logout = client.post("/api/v1/logout", json={"refresh_token": rotated})
    assert logout.status_code == 200, logout.text


def _run_schema_smoke(client) -> None:
    tokens = _login(client, "testadmin", "admin123")
    response = client.get("/api/v1/users", headers=_auth_headers(tokens["access_token"]))
    assert response.status_code == 200, response.text


def _run_idor_smoke(client, cross_org_ids: dict[str, int]) -> None:
    cases = [
        ("testorgadmin", "orgadmin123", "GET", f"/api/v1/users/{cross_org_ids['org2_user_id']}"),
        ("testadmin", "admin123", "GET", f"/api/v1/users/{cross_org_ids['org2_user_id']}"),
        ("testorgadmin", "orgadmin123", "GET", f"/api/v1/groups/{cross_org_ids['org2_group_id']}"),
        ("testadmin", "admin123", "PATCH", f"/api/v1/groups/{cross_org_ids['org2_group_id']}"),
        ("testorgadmin", "orgadmin123", "GET", f"/api/v1/api-keys/{cross_org_ids['org2_api_key_id']}"),
        ("testadmin", "admin123", "DELETE", f"/api/v1/api-keys/{cross_org_ids['org2_api_key_id']}"),
    ]
    for username, password, method, url in cases:
        tokens = _login(client, username, password)
        headers = _auth_headers(tokens["access_token"])
        if method == "GET":
            response = client.get(url, headers=headers)
        elif method == "PATCH":
            response = client.patch(url, headers=headers, json={"name": "blocked-update"})
        elif method == "DELETE":
            response = client.delete(url, headers=headers)
        else:
            raise ValueError(method)
        assert response.status_code in (403, 404, 405), (
            f"{username} {method} {url} -> {response.status_code} {response.text}"
        )


def _run_rbac_smoke(client) -> None:
    matrix = [
        ("testadmin", "admin123", "/api/v1/dashboard/admin/overview", 200),
        ("testorgadmin", "orgadmin123", "/api/v1/dashboard/organization-admin/overview", 200),
        ("test_super_admin", "TestSuperAdminPass123!", "/api/v1/dashboard/super-admin/overview", 200),
        ("testuser", "user123", "/api/v1/dashboard/user/overview", 200),
        ("testorgadmin", "orgadmin123", "/api/v1/dashboard/admin/overview", 403),
        ("testuser", "user123", "/api/v1/dashboard/admin/overview", 403),
        ("testadmin", "admin123", "/api/v1/dashboard/super-admin/overview", 403),
    ]
    for username, password, path, expected in matrix:
        tokens = _login(client, username, password)
        response = client.get(path, headers=_auth_headers(tokens["access_token"]))
        assert response.status_code == expected, (
            f"{username} GET {path} -> {response.status_code} {response.text}"
        )

    tokens = _login(client, "testuser", "user123")
    response = client.post(
        "/api/v1/admin/users/create",
        headers=_auth_headers(tokens["access_token"]),
        json={
            "username": "smoke_blocked_user",
            "email": "blocked@example.com",
            "password": "BlockedPass123!",
            "role": "user",
        },
    )
    assert response.status_code == 403, response.text


def main() -> int:
    from config.settings import settings
    from fastapi.testclient import TestClient

    print(
        "settings:",
        f"login_limit={settings.rate_limit.endpoint_limits.get('login')}",
        f"ip_limits={settings.rate_limit.enable_ip_limits}",
        f"httponly={settings.auth_cookie.use_httponly_refresh}",
        f"legacy_json={settings.auth_cookie.legacy_json_refresh}",
    )

    if not os.getenv("GITHUB_ACTIONS"):
        from scripts.ci_bootstrap_db import main as bootstrap_main

        bootstrap_main()
    else:
        print("skipping bootstrap (CI job already ran ci_bootstrap_db.py)")

    from main import app

    cross_org_ids = _load_cross_org_ids()
    checks = [
        ("auth_login_refresh_logout", lambda c: _run_auth_smoke(c)),
        ("alembic_schema_users_list", lambda c: _run_schema_smoke(c)),
        ("idor_cross_org", lambda c: _run_idor_smoke(c, cross_org_ids)),
        ("rbac_dashboard_matrix", lambda c: _run_rbac_smoke(c)),
    ]

    failures: list[str] = []
    for name, check in checks:
        try:
            with TestClient(app) as client:
                check(client)
            print("PASS", name)
        except Exception as exc:
            print("FAIL", name, exc)
            failures.append(name)

    print(f"summary: {len(checks) - len(failures)} passed, {len(failures)} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
