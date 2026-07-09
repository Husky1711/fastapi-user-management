"""CI smoke tests for authentication flows."""

from __future__ import annotations

import pytest

from tests.smoke.conftest import auth_headers, login, refresh_token_from_response

pytestmark = pytest.mark.smoke


def test_login_refresh_logout(client) -> None:
    tokens = login(client, "testuser", "user123")
    assert tokens.get("access_token")
    assert tokens.get("refresh_token")

    profile = client.get("/api/v1/profile", headers=auth_headers(tokens["access_token"]))
    assert profile.status_code == 200
    assert profile.json()["username"] == "testuser"

    client.cookies.clear()
    refresh = client.post(
        "/api/v1/refresh",
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert refresh.status_code == 200, refresh.text
    refreshed = refresh.json()
    assert refreshed.get("access_token")
    rotated_refresh = refresh_token_from_response(
        client,
        refreshed,
        tokens["refresh_token"],
        response=refresh,
    )
    assert rotated_refresh, "Refresh response must include a refresh token"

    client.cookies.clear()
    logout = client.post(
        "/api/v1/logout",
        json={"refresh_token": rotated_refresh},
    )
    assert logout.status_code == 200, logout.text


def test_alembic_head_matches_schema(client) -> None:
    """Sanity check that migrations ran (users table queryable)."""
    tokens = login(client, "testadmin", "admin123")
    response = client.get("/api/v1/users", headers=auth_headers(tokens["access_token"]))
    assert response.status_code == 200
