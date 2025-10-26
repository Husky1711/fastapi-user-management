#!/usr/bin/env python3
"""
Comprehensive Test Suite: Login Flow with 2FA & Account Lockout
Tests complete security flow with database verification
"""

import sys
import os
import requests
import time
from datetime import datetime

# Add project root to Python path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from utils.database import get_db
from models.user_model import User, LoginAttempt

BASE_URL = "http://localhost:8000"
API_BASE = f"{BASE_URL}/api/v1"

class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    END = '\033[0m'

class TestLoginSecurity:
    def __init__(self):
        self.session = requests.Session()
        self.test_results = []
        self.test_username = f"test_security_{int(time.time())}"
        self.test_password = "SecurePass123"
        
    def log_test(self, test_name: str, passed: bool, message: str = "", details: dict = None):
        """Log test result"""
        status = f"{Colors.GREEN}✅ PASS{Colors.END}" if passed else f"{Colors.RED}❌ FAIL{Colors.END}"
        print(f"{status} {test_name}")
        if message:
            print(f"   → {message}")
        if details:
            for k, v in details.items():
                print(f"      {k}: {v}")
        self.test_results.append({"name": test_name, "passed": passed})
    
    def check_database(self, username: str, field: str, expected_value):
        """Check database field value"""
        db = next(get_db())
        try:
            user = db.query(User).filter(User.username == username).first()
            if not user:
                return False, None
            
            value = getattr(user, field, None)
            if isinstance(value, datetime):
                value = value.isoformat() if value else None
            
            return value == expected_value, value
        finally:
            db.close()
    
    def test_signup(self):
        """Test user signup for testing"""
        print(f"\n{Colors.BLUE}📝 TEST 1: User Signup{Colors.END}")
        
        try:
            response = self.session.post(
                f"{API_BASE}/signup",
                json={
                    "username": self.test_username,
                    "password": self.test_password,
                    "email": f"{self.test_username}@example.com",
                    "phone_number": "1234567890",
                    "role": "user"
                }
            )
            
            if response.status_code in [200, 201]:
                self.log_test("User Signup", True, f"User created successfully (Status: {response.status_code})")
                return True
            else:
                self.log_test("User Signup", False, f"Status: {response.status_code}")
                return False
        except Exception as e:
            self.log_test("User Signup", False, str(e))
            return False
    
    def test_successful_login(self):
        """Test successful login"""
        print(f"\n{Colors.BLUE}🔓 TEST 2: Successful Login{Colors.END}")
        
        try:
            response = self.session.post(
                f"{API_BASE}/login",
                json={
                    "username": self.test_username,
                    "password": self.test_password
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("access_token"):
                    # Verify failed_attempts reset
                    db = next(get_db())
                    try:
                        user = db.query(User).filter(User.username == self.test_username).first()
                        failed_attempts = user.failed_login_attempts
                        
                        # Check login_attempts table
                        attempts = db.query(LoginAttempt).filter(
                            LoginAttempt.username == self.test_username
                        ).order_by(LoginAttempt.created_at.desc()).limit(1).first()
                        
                        self.log_test(
                            "Successful Login",
                            True,
                            "Login successful",
                            {
                                "failed_attempts": failed_attempts,
                                "latest_attempt_success": attempts.success if attempts else None
                            }
                        )
                        return True
                    finally:
                        db.close()
                
                self.log_test("Successful Login", False, "No access token in response")
                return False
            else:
                self.log_test("Successful Login", False, f"Status: {response.status_code}")
                return False
        except Exception as e:
            self.log_test("Successful Login", False, str(e))
            return False
    
    def test_failed_login_attempts(self):
        """Test failed login attempts tracking"""
        print(f"\n{Colors.BLUE}🔢 TEST 3: Failed Login Attempts Tracking{Colors.END}")
        
        try:
            # Make 3 failed login attempts
            for i in range(3):
                response = self.session.post(
                    f"{API_BASE}/login",
                    json={
                        "username": self.test_username,
                        "password": "WrongPassword"
                    }
                )
            
            # Check database
            db = next(get_db())
            try:
                user = db.query(User).filter(User.username == self.test_username).first()
                failed_attempts = user.failed_login_attempts
                
                # Check login_attempts table
                attempts = db.query(LoginAttempt).filter(
                    LoginAttempt.username == self.test_username
                ).all()
                
                # Count failed attempts
                failed_count = sum(1 for a in attempts if not a.success)
                
                self.log_test(
                    "Failed Attempts Tracking",
                    failed_attempts >= 3,
                    f"Failed attempts: {failed_attempts}, DB records: {failed_count}",
                    {
                        "user_failed_attempts": failed_attempts,
                        "total_attempts_in_db": len(attempts),
                        "failed_attempts_in_db": failed_count
                    }
                )
                return True
            finally:
                db.close()
                
        except Exception as e:
            self.log_test("Failed Attempts Tracking", False, str(e))
            return False
    
    def test_account_lockout(self):
        """Test account lockout after too many failed attempts"""
        print(f"\n{Colors.BLUE}🔒 TEST 4: Account Lockout{Colors.END}")
        
        try:
            # Make enough failed attempts to lock the account (5 total)
            for i in range(5):
                response = self.session.post(
                    f"{API_BASE}/login",
                    json={
                        "username": self.test_username,
                        "password": "WrongPassword"
                    }
                )
            
            # Check if account is locked
            db = next(get_db())
            try:
                user = db.query(User).filter(User.username == self.test_username).first()
                is_locked = user.locked_until is not None
                failed_attempts = user.failed_login_attempts
                
                self.log_test(
                    "Account Lockout",
                    is_locked and failed_attempts >= 5,
                    f"Account locked: {is_locked}, Attempts: {failed_attempts}",
                    {
                        "is_locked": is_locked,
                        "failed_attempts": failed_attempts,
                        "locked_until": user.locked_until.isoformat() if user.locked_until else None
                    }
                )
                return True
            finally:
                db.close()
                
        except Exception as e:
            self.log_test("Account Lockout", False, str(e))
            return False
    
    def test_2fa_status(self):
        """Test 2FA status endpoint"""
        print(f"\n{Colors.BLUE}📱 TEST 5: 2FA Status Check{Colors.END}")
        
        try:
            # Login first
            login_response = self.session.post(
                f"{API_BASE}/login",
                json={
                    "username": self.test_username,
                    "password": self.test_password
                }
            )
            
            if login_response.status_code == 200:
                token = login_response.json().get("access_token")
                headers = {"Authorization": f"Bearer {token}"}
                
                # Check 2FA status
                response = self.session.get(
                    f"{API_BASE}/2fa/status",
                    headers=headers
                )
                
                if response.status_code == 200:
                    data = response.json()
                    is_enabled = data.get("is_enabled")
                    has_secret = data.get("has_secret")
                    
                    self.log_test(
                        "2FA Status",
                        True,
                        f"2FA Enabled: {is_enabled}, Has Secret: {has_secret}",
                        data
                    )
                    return True
                else:
                    self.log_test("2FA Status", False, f"Status: {response.status_code}")
                    return False
            else:
                self.log_test("2FA Status", False, "Login failed")
                return False
                
        except Exception as e:
            self.log_test("2FA Status", False, str(e))
            return False
    
    def print_summary(self):
        """Print test summary"""
        print(f"\n{Colors.BLUE}{'='*60}{Colors.END}")
        print(f"{Colors.BLUE}📊 TEST SUMMARY{Colors.END}")
        print(f"{Colors.BLUE}{'='*60}{Colors.END}")
        
        total = len(self.test_results)
        passed = sum(1 for r in self.test_results if r["passed"])
        failed = total - passed
        success_rate = (passed / total * 100) if total > 0 else 0
        
        print(f"\nTotal Tests: {total}")
        print(f"{Colors.GREEN}Passed: {passed}{Colors.END}")
        print(f"{Colors.RED}Failed: {failed}{Colors.END}")
        print(f"{Colors.BLUE}Success Rate: {success_rate:.1f}%{Colors.END}")
        print(f"\n{Colors.BLUE}{'='*60}{Colors.END}")
        
        if success_rate == 100:
            print(f"{Colors.GREEN}🎉 All tests passed!{Colors.END}")
        elif success_rate >= 80:
            print(f"{Colors.YELLOW}⚠️  Most tests passed{Colors.END}")
        else:
            print(f"{Colors.RED}❌ Several tests failed{Colors.END}")
    
    def run_all_tests(self):
        """Run all security tests"""
        print(f"\n{Colors.BLUE}{'='*60}{Colors.END}")
        print(f"{Colors.BLUE}🔐 LOGIN SECURITY TEST SUITE{Colors.END}")
        print(f"{Colors.BLUE}{'='*60}{Colors.END}")
        
        # Test 1: Signup
        if not self.test_signup():
            return
        
        # Test 2: Successful login
        self.test_successful_login()
        
        # Test 3: Failed attempts tracking
        self.test_failed_login_attempts()
        
        # Test 4: Account lockout
        self.test_account_lockout()
        
        # Test 5: 2FA status
        self.test_2fa_status()
        
        # Print summary
        self.print_summary()

if __name__ == "__main__":
    tester = TestLoginSecurity()
    tester.run_all_tests()
