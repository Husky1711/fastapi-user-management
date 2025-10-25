"""
Sample Integration Tests

This demonstrates how to write integration tests for service interactions.
"""

import pytest
from fastapi.testclient import TestClient
from tests.utils.test_helpers import TestClientManager, get_auth_headers


@pytest.mark.integration
@pytest.mark.auth
class TestAuthIntegration:
    """Integration tests for authentication flow"""
    
    def test_login_flow(self, test_client_manager):
        """Test complete login flow"""
        client = test_client_manager.client
        
        # Test login
        login_data = {
            "username": "test_auth_user",
            "password": "NewSecurePass123"
        }
        
        response = client.post("/api/v1/login", json=login_data)
        assert response.status_code == 200
        
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert "user_id" in data
    
    def test_refresh_token_flow(self, test_client_manager):
        """Test refresh token flow"""
        client = test_client_manager.client
        
        # Login first
        login_data = {
            "username": "test_auth_user", 
            "password": "NewSecurePass123"
        }
        response = client.post("/api/v1/login", json=login_data)
        assert response.status_code == 200
        
        refresh_token = response.json().get("refresh_token")
        
        # Test refresh
        refresh_data = {"refresh_token": refresh_token}
        response = client.post("/api/v1/refresh", json=refresh_data)
        assert response.status_code == 200
        
        new_data = response.json()
        assert "access_token" in new_data
        assert "refresh_token" in new_data


@pytest.mark.integration
@pytest.mark.users
class TestUserManagementIntegration:
    """Integration tests for user management"""
    
    def test_user_profile_flow(self, test_client_manager):
        """Test user profile management flow"""
        client = test_client_manager.client
        
        # Get auth headers
        headers = get_auth_headers(client, "test_auth_user", "NewSecurePass123")
        assert headers  # Should have auth headers
        
        # Test get profile
        response = client.get("/api/v1/profile", headers=headers)
        assert response.status_code == 200
        
        profile_data = response.json()
        assert "username" in profile_data
        assert "email" in profile_data
    
    def test_password_change_flow(self, test_client_manager):
        """Test password change flow"""
        client = test_client_manager.client
        
        headers = get_auth_headers(client, "test_auth_user", "NewSecurePass123")
        
        # Test password change
        password_data = {
            "current_password": "NewSecurePass123",
            "new_password": "AnotherNewPass123"
        }
        
        response = client.post("/api/v1/password/change", json=password_data, headers=headers)
        assert response.status_code == 200
