"""
RBAC smoke tests — dashboard role × route matrix.

These encode product intent: each staff role uses its own dashboard prefix.
See docs/DASHBOARD_ROLE_MATRIX.md.
"""

from __future__ import annotations

import pytest

from conftest import auth_headers, login

pytestmark = pytest.mark.smoke


@pytest.mark.parametrize(
    ("username", "password", "path", "expected_status"),
    [
        ("testadmin", "admin123", "/api/v1/dashboard/admin/overview", 200),
        ("testorgadmin", "orgadmin123", "/api/v1/dashboard/organization-admin/overview", 200),
        ("test_super_admin", "TestSuperAdminPass123!", "/api/v1/dashboard/super-admin/overview", 200),
        ("testuser", "user123", "/api/v1/dashboard/user/overview", 200),
        # Cross-role denials — intentional separation of dashboard surfaces
        ("testorgadmin", "orgadmin123", "/api/v1/dashboard/admin/overview", 403),
        ("testuser", "user123", "/api/v1/dashboard/admin/overview", 403),
        ("testadmin", "admin123", "/api/v1/dashboard/super-admin/overview", 403),
    ],
)
def test_dashboard_role_matrix(
    client,
    username: str,
    password: str,
    path: str,
    expected_status: int,
) -> None:
    tokens = login(client, username, password)
    response = client.get(path, headers=auth_headers(tokens["access_token"]))
    assert response.status_code == expected_status, response.text


def test_user_cannot_create_users(client) -> None:
    tokens = login(client, "testuser", "user123")
    response = client.post(
        "/api/v1/admin/users/create",
        headers=auth_headers(tokens["access_token"]),
        json={
            "username": "smoke_blocked_user",
            "email": "blocked@example.com",
            "password": "BlockedPass123!",
            "role": "user",
        },
    )
    assert response.status_code == 403
