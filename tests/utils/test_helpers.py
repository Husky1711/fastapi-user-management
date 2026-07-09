"""
Test Utilities

Common utilities and helpers for testing.
"""

import pytest
import asyncio
from typing import Dict, Any, Optional
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from utils.database import get_db
from models.user_model import User


def _get_app():
    from main import app

    return app


class TestClientManager:
    """Manages test client and database sessions"""
    
    def __init__(self):
        self.client = TestClient(_get_app())
        self.db_session: Optional[Session] = None
    
    def get_db_session(self) -> Session:
        """Get database session for testing"""
        if not self.db_session:
            self.db_session = next(get_db())
        return self.db_session
    
    def cleanup(self):
        """Cleanup test resources"""
        if self.db_session:
            self.db_session.close()


@pytest.fixture
def test_client_manager():
    """Fixture for test client manager"""
    manager = TestClientManager()
    yield manager
    manager.cleanup()


@pytest.fixture
def db_session(test_client_manager):
    """Fixture for database session"""
    return test_client_manager.get_db_session()


@pytest.fixture
def test_user_data():
    """Fixture for test user data"""
    return {
        "username": "test_user",
        "email": "test@example.com",
        "password": "TestPass123",
        "phone_number": "1234567890",
        "role": "user"
    }


@pytest.fixture
def admin_user_data():
    """Fixture for admin user data"""
    return {
        "username": "admin_user",
        "email": "admin@example.com", 
        "password": "AdminPass123",
        "phone_number": "9876543210",
        "role": "admin"
    }


def create_test_user(db: Session, user_data: Dict[str, Any]) -> User:
    """Helper to create a test user"""
    user = User(**user_data)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def cleanup_test_user(db: Session, username: str):
    """Helper to cleanup test user"""
    user = db.query(User).filter(User.username == username).first()
    if user:
        db.delete(user)
        db.commit()


def get_auth_headers(client: TestClient, username: str, password: str) -> Dict[str, str]:
    """Helper to get authentication headers"""
    response = client.post("/api/v1/login", json={"username": username, "password": password})
    if response.status_code == 200:
        token = response.json().get("access_token")
        return {"Authorization": f"Bearer {token}"}
    return {}


class AsyncTestMixin:
    """Mixin for async test support"""
    
    @pytest.fixture(scope="session")
    def event_loop(self):
        """Create an instance of the default event loop for the test session."""
        loop = asyncio.get_event_loop_policy().new_event_loop()
        yield loop
        loop.close()
