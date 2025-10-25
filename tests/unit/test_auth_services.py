"""
Sample Unit Tests for Auth Services

This demonstrates how to write unit tests for individual services.
"""

import pytest
from unittest.mock import Mock, patch
from services.auth import AuthService
from services.users import UserService


@pytest.mark.unit
@pytest.mark.auth
class TestAuthService:
    """Unit tests for AuthService"""
    
    def test_password_hashing(self):
        """Test password hashing functionality"""
        auth_service = AuthService()
        password = "TestPassword123"
        
        hashed = auth_service.hash_password(password)
        
        assert hashed != password
        assert len(hashed) > 0
        assert auth_service.verify_password(password, hashed)
    
    def test_password_verification_failure(self):
        """Test password verification with wrong password"""
        auth_service = AuthService()
        password = "TestPassword123"
        wrong_password = "WrongPassword123"
        
        hashed = auth_service.hash_password(password)
        
        assert not auth_service.verify_password(wrong_password, hashed)


@pytest.mark.unit
@pytest.mark.users
class TestUserService:
    """Unit tests for UserService"""
    
    def test_username_validation(self):
        """Test username validation"""
        user_service = UserService()
        
        # Valid usernames
        assert user_service.validate_username("validuser") == True
        assert user_service.validate_username("user123") == True
        assert user_service.validate_username("user_name") == True
        
        # Invalid usernames
        assert user_service.validate_username("") == False
        assert user_service.validate_username("a") == False  # Too short
        assert user_service.validate_username("user@name") == False  # Invalid char
    
    def test_email_validation(self):
        """Test email validation"""
        user_service = UserService()
        
        # Valid emails
        assert user_service.validate_email("test@example.com") == True
        assert user_service.validate_email("user.name@domain.co.uk") == True
        
        # Invalid emails
        assert user_service.validate_email("invalid-email") == False
        assert user_service.validate_email("@domain.com") == False
        assert user_service.validate_email("user@") == False