"""
Test Fixtures

Contains test data, mock objects, and fixtures used across tests.
"""

import pytest
from typing import Dict, Any, List
from faker import Faker

fake = Faker()


@pytest.fixture
def sample_users_data():
    """Fixture for sample users data"""
    return [
        {
            "username": "test_user_1",
            "email": "user1@example.com",
            "password": "TestPass123",
            "phone_number": "1234567890",
            "role": "user"
        },
        {
            "username": "test_admin_1", 
            "email": "admin1@example.com",
            "password": "AdminPass123",
            "phone_number": "9876543210",
            "role": "admin"
        },
        {
            "username": "test_org_admin_1",
            "email": "orgadmin1@example.com", 
            "password": "OrgAdminPass123",
            "phone_number": "5555555555",
            "role": "organization_admin"
        }
    ]


@pytest.fixture
def fake_user_data():
    """Fixture for fake user data using Faker"""
    return {
        "username": fake.user_name(),
        "email": fake.email(),
        "password": fake.password(),
        "phone_number": fake.phone_number(),
        "role": fake.random_element(elements=("user", "admin", "organization_admin"))
    }


@pytest.fixture
def login_scenarios():
    """Fixture for different login scenarios"""
    return {
        "valid_login": {
            "username": "test_auth_user",
            "password": "NewSecurePass123"
        },
        "invalid_password": {
            "username": "test_auth_user", 
            "password": "WrongPassword123"
        },
        "invalid_username": {
            "username": "nonexistent_user",
            "password": "SomePassword123"
        },
        "empty_credentials": {
            "username": "",
            "password": ""
        }
    }


@pytest.fixture
def session_strategies():
    """Fixture for session control strategies"""
    return [
        "allow_multiple",
        "replace_all", 
        "replace_same_device",
        "deny_if_exists",
        "limit_sessions"
    ]


@pytest.fixture
def api_endpoints():
    """Fixture for API endpoints to test"""
    return {
        "auth": [
            "/api/v1/login",
            "/api/v1/signup", 
            "/api/v1/refresh",
            "/api/v1/logout",
            "/api/v1/logout-all"
        ],
        "users": [
            "/api/v1/users",
            "/api/v1/profile",
            "/api/v1/admin/users/create"
        ],
        "sessions": [
            "/api/v1/sessions",
            "/api/v1/sessions/info",
            "/api/v1/sessions/revoke-others"
        ],
        "production": [
            "/api/v1/audit/logs",
            "/api/v1/audit/statistics",
            "/api/v1/permissions",
            "/api/v1/groups",
            "/api/v1/api-keys"
        ]
    }


@pytest.fixture
def error_responses():
    """Fixture for expected error responses"""
    return {
        "unauthorized": {"status_code": 401, "detail": "Unauthorized"},
        "forbidden": {"status_code": 403, "detail": "Forbidden"},
        "not_found": {"status_code": 404, "detail": "Not Found"},
        "validation_error": {"status_code": 422, "detail": "Validation Error"},
        "rate_limited": {"status_code": 429, "detail": "Rate Limited"}
    }
