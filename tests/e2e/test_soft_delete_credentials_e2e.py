"""
E2E (HTTP): H5 soft-delete credential cleanup.

Exercises real API routes — login, refresh, bearer, API key, admin soft-delete —
not service-layer calls.
"""

from __future__ import annotations

import os
import uuid

import pytest
from fastapi.testclient import TestClient

from tests.utils.csrf import CSRF_HEADERS

pytestmark = [pytest.mark.e2e, pytest.mark.auth]


@pytest.fixture(scope="module")
def client():
    if not os.getenv("GITHUB_ACTIONS"):
        from scripts.ci_bootstrap_db import main as bootstrap

        bootstrap()

    # Soften rate limits for multi-step e2e
    os.environ.setdefault("RATE_LIMIT__ENABLE_IP_LIMITS", "false")
    os.environ.setdefault("RATE_LIMIT__ENABLE_USER_LIMITS", "false")

    from main import app

    with TestClient(app) as test_client:
        yield test_client


def _login(client: TestClient, username: str, password: str) -> dict:
    client.cookies.clear()
    response = client.post(
        "/api/v1/login",
        json={"username": username, "password": password},
        headers=CSRF_HEADERS,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    # Cookie-first refresh still returns access_token in JSON
    assert body.get("access_token"), body
    return body


def _refresh_token(client: TestClient, body: dict, response=None) -> str | None:
    token = body.get("refresh_token")
    if token:
        return token
    if response is not None:
        cookie = response.cookies.get("refresh_token")
        if cookie:
            return cookie
    return client.cookies.get("refresh_token")


def _auth(access_token: str) -> dict:
    return {**CSRF_HEADERS, "Authorization": f"Bearer {access_token}"}


@pytest.mark.e2e
def test_e2e_soft_delete_kills_login_refresh_bearer_and_api_key(client: TestClient):
    suffix = uuid.uuid4().hex[:10]
    username = f"e2eh5_{suffix}"
    email = f"e2eh5_{suffix}@example.com"
    password = "E2ePass123!"

    # 1) Admin login
    admin = _login(client, "test_super_admin", "TestSuperAdminPass123!")
    admin_headers = _auth(admin["access_token"])

    # 2) Create victim user via admin API
    create = client.post(
        "/api/v1/admin/users/create",
        headers=admin_headers,
        json={
            "username": username,
            "email": email,
            "password": password,
            "role": "user",
            "organization_id": 1,
            "auto_generate_password": False,
            "send_welcome_email": False,
        },
    )
    assert create.status_code in (200, 201), create.text
    create_body = create.json()
    user_payload = create_body.get("user") or {}
    user_id = user_payload.get("id") or create_body.get("user_id")
    assert user_id, create_body

    # 3) Victim logs in
    victim_login_resp = client.post(
        "/api/v1/login",
        json={"username": username, "password": password},
        headers=CSRF_HEADERS,
    )
    assert victim_login_resp.status_code == 200, victim_login_resp.text
    victim = victim_login_resp.json()
    victim_access = victim["access_token"]
    victim_refresh = _refresh_token(client, victim, victim_login_resp)
    assert victim_refresh, victim

    # Bearer works before delete
    whoami_jwt = client.get(
        "/api/v1/integration/whoami",
        headers=_auth(victim_access),
    )
    assert whoami_jwt.status_code == 200, whoami_jwt.text

    # 4) Admin issues API key for victim
    key_resp = client.post(
        "/api/v1/api-keys",
        headers=admin_headers,
        json={
            "key_name": f"e2e-h5-{suffix}",
            "user_id": user_id,
            "permissions": ["read:users"],
        },
    )
    assert key_resp.status_code == 200, key_resp.text
    key_body = key_resp.json()
    raw_api_key = key_body.get("key_value")
    assert raw_api_key, key_body

    whoami_key = client.get(
        "/api/v1/integration/whoami",
        headers={**CSRF_HEADERS, "X-API-Key": raw_api_key},
    )
    assert whoami_key.status_code == 200, whoami_key.text

    # 5) Soft-delete via HTTP
    # Re-login admin in case token/cookie jar mixed with victim
    admin = _login(client, "test_super_admin", "TestSuperAdminPass123!")
    admin_headers = _auth(admin["access_token"])
    delete_resp = client.delete(
        f"/api/v1/users/{user_id}",
        headers=admin_headers,
    )
    assert delete_resp.status_code == 200, delete_resp.text
    assert delete_resp.json().get("success") is True

    # 6) Login fails
    login_after = client.post(
        "/api/v1/login",
        json={"username": username, "password": password},
        headers=CSRF_HEADERS,
    )
    assert login_after.status_code in (401, 403), login_after.text

    # 7) Refresh fails (cookie or body)
    client.cookies.clear()
    refresh_after = client.post(
        "/api/v1/refresh",
        headers=CSRF_HEADERS,
        json={"refresh_token": victim_refresh},
    )
    assert refresh_after.status_code == 401, refresh_after.text

    # 8) Bearer access fails
    bearer_after = client.get(
        "/api/v1/integration/whoami",
        headers=_auth(victim_access),
    )
    assert bearer_after.status_code == 401, bearer_after.text

    # 9) API key fails
    key_after = client.get(
        "/api/v1/integration/whoami",
        headers={**CSRF_HEADERS, "X-API-Key": raw_api_key},
    )
    assert key_after.status_code == 401, key_after.text

    # 10) Reuse of revoked refresh still fails
    reuse = client.post(
        "/api/v1/refresh",
        headers=CSRF_HEADERS,
        json={"refresh_token": victim_refresh},
    )
    assert reuse.status_code == 401, reuse.text
