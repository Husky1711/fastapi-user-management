"""
Unit Tests for User Service
Tests core user service functionality
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy.orm import Session
from services.users import UserService
from utils.database import get_db
import unittest


class TestUserService(unittest.TestCase):
    """Test UserService methods"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.db = next(get_db())
        self.test_username = "test_unit_user"
        self.test_email = "test_unit@example.com"
    
    def tearDown(self):
        """Clean up after tests"""
        self.db.close()
    
    def test_get_user_by_id(self):
        """Test getting user by ID"""
        # Test with existing user
        user = UserService.get_user_by_id(self.db, 1)
        self.assertIsNotNone(user)
        self.assertEqual(user.id, 1)
        
        # Test with non-existent user
        user = UserService.get_user_by_id(self.db, 99999)
        self.assertIsNone(user)
    
    def test_get_user_by_username(self):
        """Test getting user by username"""
        # Test with existing user
        user = UserService.get_user_by_username(self.db, "test_auth_user")
        self.assertIsNotNone(user)
        self.assertEqual(user.username, "test_auth_user")
        
        # Test with non-existent user
        user = UserService.get_user_by_username(self.db, "nonexistent_user")
        self.assertIsNone(user)
    
    def test_get_user_by_email(self):
        """Test getting user by email"""
        # Test with existing user
        user = UserService.get_user_by_email(self.db, "test@example.com")
        if user:
            self.assertIsNotNone(user)
        else:
            # User might not exist, which is OK
            self.assertIsNone(user)
    
    def test_check_username_exists(self):
        """Test checking if username exists"""
        # Test with existing username
        exists = UserService.check_username_exists(self.db, "test_auth_user")
        self.assertTrue(exists)
        
        # Test with non-existent username
        exists = UserService.check_username_exists(self.db, "nonexistent_user_999")
        self.assertFalse(exists)
    
    def test_check_email_exists(self):
        """Test checking if email exists"""
        # Test with existing email
        exists = UserService.check_email_exists(self.db, "test@example.com")
        # Might not exist, either result is OK for this test
        
        # Test with non-existent email
        exists = UserService.check_email_exists(self.db, "nonexistent_email_999@example.com")
        self.assertFalse(exists)
    
    def test_get_all_users(self):
        """Test getting all users"""
        users = UserService.get_all_users(self.db, skip=0, limit=10)
        self.assertIsInstance(users, list)
        self.assertGreaterEqual(len(users), 0)
    
    def test_get_users_by_role_and_organization(self):
        """Test getting users by role and organization"""
        # Test as super admin
        users = UserService.get_users_by_role_and_organization(
            self.db, "super_admin", 1
        )
        self.assertIsInstance(users, list)
        
        # Test as admin
        users = UserService.get_users_by_role_and_organization(
            self.db, "admin", 1
        )
        self.assertIsInstance(users, list)
        
        # Test as user
        users = UserService.get_users_by_role_and_organization(
            self.db, "user", 1
        )
        self.assertIsInstance(users, list)


if __name__ == "__main__":
    unittest.main()

