"""
Sample Integration Tests

This demonstrates how to write integration tests for service interactions.
"""

import pytest
from fastapi.testclient import TestClient
from tests.utils.test_helpers import TestClientManager, get_auth_headers
from tests.utils.csrf import CSRF_HEADERS


@pytest.mark.integration
@pytest.mark.auth
class TestAuthIntegration:
    """Integration tests for authentication flow"""

    def test_login_flow(self, test_client_manager):
        """Test complete login flow"""
        client = test_client_manager.client

        login_data = {
            "username": "testuser",
            "password": "user123",
        }

        response = client.post("/api/v1/login", json=login_data)
        assert response.status_code == 200

        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data.get("token_type") == "bearer"

    def test_refresh_token_flow(self, test_client_manager):
        """Test refresh token flow"""
        client = test_client_manager.client

        login_data = {
            "username": "testuser",
            "password": "user123",
        }
        response = client.post("/api/v1/login", json=login_data)
        assert response.status_code == 200

        refresh_token = response.json().get("refresh_token")

        response = client.post(
            "/api/v1/refresh",
            json={"refresh_token": refresh_token},
            headers=CSRF_HEADERS,
        )
        assert response.status_code == 200

        new_data = response.json()
        assert "access_token" in new_data
        assert "refresh_token" in new_data

    def test_revoke_other_sessions_keeps_current(self, test_client_manager):
        """Revoke-others should keep the caller's session and revoke others."""
        from config.settings import settings
        from tests.utils.test_helpers import _get_app

        login_data = {
            "username": "testuser",
            "password": "user123",
        }

        client_a = TestClient(_get_app())
        client_b = TestClient(_get_app())

        response_a = client_a.post("/api/v1/login", json=login_data)
        response_b = client_b.post("/api/v1/login", json=login_data)
        assert response_a.status_code == 200
        assert response_b.status_code == 200

        token_a = response_a.json()["access_token"]
        refresh_a = response_a.json()["refresh_token"]
        refresh_b = response_b.json()["refresh_token"]
        assert refresh_a and refresh_b and refresh_a != refresh_b

        # Route resolves current session from httpOnly cookie (not JSON body).
        cookie_name = settings.auth_cookie.name
        client_a.cookies.set(cookie_name, refresh_a)
        client_b.cookies.set(cookie_name, refresh_b)

        revoke_response = client_a.post(
            "/api/v1/sessions/revoke-others",
            headers={"Authorization": f"Bearer {token_a}"},
        )
        assert revoke_response.status_code == 200
        assert "Revoked" in revoke_response.json().get("message", "")

        kept_refresh = client_a.post(
            "/api/v1/refresh",
            json={"refresh_token": refresh_a},
            headers=CSRF_HEADERS,
        )
        assert kept_refresh.status_code == 200
        assert kept_refresh.json().get("access_token")

        revoked_refresh = client_b.post(
            "/api/v1/refresh",
            json={"refresh_token": refresh_b},
            headers=CSRF_HEADERS,
        )
        assert revoked_refresh.status_code == 401


@pytest.mark.integration
@pytest.mark.users
class TestUserManagementIntegration:
    """Integration tests for user management"""

    def test_user_profile_flow(self, test_client_manager):
        """Test user profile management flow"""
        client = test_client_manager.client

        headers = get_auth_headers(client, "testuser", "user123")
        assert headers

        response = client.get("/api/v1/profile", headers=headers)
        assert response.status_code == 200

        profile_data = response.json()
        assert "username" in profile_data
        assert "email" in profile_data

    def test_password_change_flow(self, test_client_manager):
        """Test password change flow"""
        client = test_client_manager.client

        headers = get_auth_headers(client, "testuser", "user123")

        password_data = {
            "current_password": "TotallyWrongPass123!",
            "new_password": "AnotherNewPass123!",
        }

        response = client.post(
            "/api/v1/password/change", json=password_data, headers=headers
        )
        assert response.status_code == 400
        assert "incorrect" in response.json().get("detail", "").lower()
