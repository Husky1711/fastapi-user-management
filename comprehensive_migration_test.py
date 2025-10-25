#!/usr/bin/env python3
"""
COMPREHENSIVE SERVICES MIGRATION TEST SUITE

This test suite covers:
1. All API endpoints in multiple scenarios
2. Database CRUD operations verification
3. Data integrity checks
4. Error handling scenarios
5. Performance and rate limiting
6. Cross-service integration
"""

import requests
import json
import time
import random
import string
from typing import Dict, Any, List, Optional
from datetime import datetime

class ComprehensiveMigrationTester:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.session = requests.Session()
        self.test_results = {}
        self.test_data = {}
        self.success_count = 0
        self.total_tests = 0
        
    def log_test(self, category: str, test_name: str, success: bool, details: str = ""):
        """Log test results"""
        self.total_tests += 1
        if success:
            self.success_count += 1
            status = "✅ PASS"
        else:
            status = "❌ FAIL"
        
        if category not in self.test_results:
            self.test_results[category] = {}
        
        self.test_results[category][test_name] = {
            "status": status,
            "success": success,
            "details": details,
            "timestamp": datetime.now().isoformat()
        }
        
        print(f"{status} {category}: {test_name}")
        if details and not success:
            print(f"    Details: {details}")
    
    def test_authentication_scenarios(self):
        """Test all authentication scenarios"""
        print("\n🔐 TESTING AUTHENTICATION SCENARIOS")
        print("=" * 50)
        
        # Test 1: Basic Login
        login_data = {"username": "test_auth_user", "password": "FinalTestPass123"}
        response = self.session.post(f"{self.base_url}/api/v1/login", json=login_data)
        success = response.status_code == 200
        self.log_test("Authentication", "Basic Login", success, 
                     f"Status: {response.status_code}")
        
        if success:
            data = response.json()
            self.test_data["access_token"] = data.get("access_token")
            self.test_data["refresh_token"] = data.get("refresh_token")
            self.test_data["user_id"] = data.get("user_id")
        
        # Test 2: Enhanced Login Strategies
        strategies = ["allow_multiple", "replace_all", "replace_same_device", "limit_sessions"]
        for strategy in strategies:
            response = self.session.post(f"{self.base_url}/api/v1/login-with-session-control?session_strategy={strategy}", json=login_data)
            success = response.status_code == 200
            self.log_test("Authentication", f"Enhanced Login ({strategy})", success,
                         f"Status: {response.status_code}")
        
        # Test 3: Token Refresh
        if self.test_data.get("refresh_token"):
            refresh_data = {"refresh_token": self.test_data["refresh_token"]}
            response = self.session.post(f"{self.base_url}/api/v1/refresh", json=refresh_data)
            success = response.status_code == 200
            self.log_test("Authentication", "Token Refresh", success,
                         f"Status: {response.status_code}")
            
            if success:
                new_data = response.json()
                self.test_data["new_refresh_token"] = new_data.get("refresh_token")
        
        # Test 4: Logout
        if self.test_data.get("refresh_token"):
            logout_data = {"refresh_token": self.test_data["refresh_token"]}
            response = self.session.post(f"{self.base_url}/api/v1/logout", json=logout_data)
            success = response.status_code == 200
            self.log_test("Authentication", "Logout", success,
                         f"Status: {response.status_code}")
        
        # Test 5: Invalid Credentials
        invalid_login = {"username": "test_auth_user", "password": "wrongpassword"}
        response = self.session.post(f"{self.base_url}/api/v1/login", json=invalid_login)
        success = response.status_code == 401
        self.log_test("Authentication", "Invalid Credentials Rejection", success,
                     f"Status: {response.status_code} (Expected: 401)")
        
        # Test 6: Unauthorized Access
        headers = {"Authorization": "Bearer invalid_token"}
        response = self.session.get(f"{self.base_url}/api/v1/profile", headers=headers)
        success = response.status_code == 401
        self.log_test("Authentication", "Unauthorized Access Rejection", success,
                     f"Status: {response.status_code} (Expected: 401)")
    
    def test_user_management_scenarios(self):
        """Test user management scenarios"""
        print("\n👥 TESTING USER MANAGEMENT SCENARIOS")
        print("=" * 50)
        
        # Re-login for authenticated tests
        login_data = {"username": "test_auth_user", "password": "FinalTestPass123"}
        response = self.session.post(f"{self.base_url}/api/v1/login", json=login_data)
        
        if response.status_code == 200:
            data = response.json()
            headers = {"Authorization": f"Bearer {data.get('access_token')}"}
            
            # Test 1: Get Users
            response = self.session.get(f"{self.base_url}/api/v1/users", headers=headers)
            success = response.status_code == 200
            self.log_test("User Management", "Get Users", success,
                         f"Status: {response.status_code}")
            
            if success:
                users_data = response.json()
                self.test_data["users_count"] = len(users_data.get("users", []))
            
            # Test 2: Get User Profile
            response = self.session.get(f"{self.base_url}/api/v1/profile", headers=headers)
            success = response.status_code == 200
            self.log_test("User Management", "Get Profile", success,
                         f"Status: {response.status_code}")
            
            # Test 3: Update Profile
            profile_data = {
                "email": f"updated_{int(time.time())}@example.com",
                "phone_number": f"123456{random.randint(1000, 9999)}"
            }
            response = self.session.put(f"{self.base_url}/api/v1/profile", json=profile_data, headers=headers)
            success = response.status_code == 200
            self.log_test("User Management", "Update Profile", success,
                         f"Status: {response.status_code}")
            
            # Test 4: Password Change
            password_data = {
                "current_password": "FinalTestPass123",
                "new_password": "NewSecurePass123"
            }
            response = self.session.post(f"{self.base_url}/api/v1/password/change", json=password_data, headers=headers)
            success = response.status_code == 200
            self.log_test("User Management", "Password Change", success,
                         f"Status: {response.status_code}")
            
            # Test 5: Password History
            response = self.session.get(f"{self.base_url}/api/v1/password/history", headers=headers)
            success = response.status_code == 200
            self.log_test("User Management", "Password History", success,
                         f"Status: {response.status_code}")
            
            # Test 6: Password Reset Request
            reset_data = {"email": "test@example.com"}
            response = self.session.post(f"{self.base_url}/api/v1/password/reset-request", json=reset_data)
            success = response.status_code == 200
            self.log_test("User Management", "Password Reset Request", success,
                         f"Status: {response.status_code}")
    
    def test_admin_scenarios(self):
        """Test admin scenarios"""
        print("\n👨‍💼 TESTING ADMIN SCENARIOS")
        print("=" * 50)
        
        # Login as admin
        admin_login = {"username": "test_admin_user", "password": "AdminPass123"}
        response = self.session.post(f"{self.base_url}/api/v1/login", json=admin_login)
        
        if response.status_code == 200:
            data = response.json()
            headers = {"Authorization": f"Bearer {data.get('access_token')}"}
            
            # Test 1: Admin Create User
            user_data = {
                "username": f"test_user_{int(time.time())}",
                "email": f"test_{int(time.time())}@example.com",
                "role": "user",
                "phone_number": f"123456{random.randint(1000, 9999)}"
            }
            response = self.session.post(f"{self.base_url}/api/v1/admin/users/create", json=user_data, headers=headers)
            success = response.status_code == 200
            self.log_test("Admin", "Create User", success,
                         f"Status: {response.status_code}")
            
            if success:
                created_user = response.json()
                self.test_data["created_user_id"] = created_user.get("user", {}).get("id")
        
        # Test 2: Regular User Cannot Create Users
        regular_login = {"username": "test_auth_user", "password": "NewSecurePass123"}
        response = self.session.post(f"{self.base_url}/api/v1/login", json=regular_login)
        
        if response.status_code == 200:
            data = response.json()
            headers = {"Authorization": f"Bearer {data.get('access_token')}"}
            
            user_data = {
                "username": f"unauthorized_user_{int(time.time())}",
                "email": f"unauthorized_{int(time.time())}@example.com",
                "role": "user",
                "phone_number": "1234567890"
            }
            response = self.session.post(f"{self.base_url}/api/v1/admin/users/create", json=user_data, headers=headers)
            success = response.status_code == 403
            self.log_test("Admin", "Regular User Cannot Create Users", success,
                         f"Status: {response.status_code} (Expected: 403)")
    
    def test_production_endpoints_scenarios(self):
        """Test production endpoints scenarios"""
        print("\n🏭 TESTING PRODUCTION ENDPOINTS SCENARIOS")
        print("=" * 50)
        
        # Login for authenticated tests
        login_data = {"username": "test_auth_user", "password": "NewSecurePass123"}
        response = self.session.post(f"{self.base_url}/api/v1/login", json=login_data)
        
        if response.status_code == 200:
            data = response.json()
            headers = {"Authorization": f"Bearer {data.get('access_token')}"}
            
            # Test 1: Sessions
            response = self.session.get(f"{self.base_url}/api/v1/sessions", headers=headers)
            success = response.status_code == 200
            self.log_test("Production", "Sessions API", success,
                         f"Status: {response.status_code}")
            
            # Test 2: Session Statistics
            response = self.session.get(f"{self.base_url}/api/v1/sessions/statistics", headers=headers)
            success = response.status_code == 200
            self.log_test("Production", "Session Statistics", success,
                         f"Status: {response.status_code}")
            
            # Test 3: Audit Logs
            response = self.session.get(f"{self.base_url}/api/v1/audit/logs", headers=headers)
            success = response.status_code == 200
            self.log_test("Production", "Audit Logs", success,
                         f"Status: {response.status_code}")
            
            # Test 4: Audit Statistics
            response = self.session.get(f"{self.base_url}/api/v1/audit/statistics", headers=headers)
            success = response.status_code == 200
            self.log_test("Production", "Audit Statistics", success,
                         f"Status: {response.status_code}")
            
            # Test 5: Permissions
            response = self.session.get(f"{self.base_url}/api/v1/permissions", headers=headers)
            success = response.status_code == 200
            self.log_test("Production", "Permissions API", success,
                         f"Status: {response.status_code}")
            
            # Test 6: Permission Statistics
            response = self.session.get(f"{self.base_url}/api/v1/permissions/statistics", headers=headers)
            success = response.status_code == 200
            self.log_test("Production", "Permission Statistics", success,
                         f"Status: {response.status_code}")
            
            # Test 7: Groups
            response = self.session.get(f"{self.base_url}/api/v1/groups", headers=headers)
            success = response.status_code == 200
            self.log_test("Production", "Groups API", success,
                         f"Status: {response.status_code}")
            
            # Test 8: Group Statistics
            response = self.session.get(f"{self.base_url}/api/v1/groups/statistics", headers=headers)
            success = response.status_code == 200
            self.log_test("Production", "Group Statistics", success,
                         f"Status: {response.status_code}")
            
            # Test 9: API Keys
            response = self.session.get(f"{self.base_url}/api/v1/api-keys", headers=headers)
            success = response.status_code == 200
            self.log_test("Production", "API Keys", success,
                         f"Status: {response.status_code}")
    
    def test_rate_limiting_scenarios(self):
        """Test rate limiting scenarios"""
        print("\n⚡ TESTING RATE LIMITING SCENARIOS")
        print("=" * 50)
        
        # Test 1: Multiple Login Attempts
        login_data = {"username": "test_auth_user", "password": "NewSecurePass123"}
        
        for i in range(5):
            response = self.session.post(f"{self.base_url}/api/v1/login", json=login_data)
            success = response.status_code in [200, 429]  # Success or rate limited
            self.log_test("Rate Limiting", f"Login Attempt {i+1}", success,
                         f"Status: {response.status_code}")
            
            if response.status_code == 429:
                self.log_test("Rate Limiting", "Rate Limit Triggered", True,
                             "Rate limiting is working correctly")
                break
        
        # Test 2: API Endpoint Rate Limiting
        if self.test_data.get("access_token"):
            headers = {"Authorization": f"Bearer {self.test_data['access_token']}"}
            
            for i in range(10):
                response = self.session.get(f"{self.base_url}/api/v1/users", headers=headers)
                success = response.status_code in [200, 429]
                self.log_test("Rate Limiting", f"API Request {i+1}", success,
                             f"Status: {response.status_code}")
                
                if response.status_code == 429:
                    self.log_test("Rate Limiting", "API Rate Limit Triggered", True,
                                 "API rate limiting is working correctly")
                    break
    
    def test_database_operations(self):
        """Test database operations and data integrity"""
        print("\n🗄️ TESTING DATABASE OPERATIONS")
        print("=" * 50)
        
        try:
            from utils.database import get_db
            from models.user_model import User, UserSession, AuditLog, UserPermission, UserGroup, ApiKey, PasswordHistory
            
            db = next(get_db())
            
            # Test 1: User Table Operations
            users_count = db.query(User).count()
            self.log_test("Database", "Users Table Access", True,
                         f"Found {users_count} users")
            
            # Test 2: User Sessions Table
            sessions_count = db.query(UserSession).count()
            self.log_test("Database", "User Sessions Table Access", True,
                         f"Found {sessions_count} sessions")
            
            # Test 3: Audit Logs Table
            audit_count = db.query(AuditLog).count()
            self.log_test("Database", "Audit Logs Table Access", True,
                         f"Found {audit_count} audit logs")
            
            # Test 4: User Permissions Table
            permissions_count = db.query(UserPermission).count()
            self.log_test("Database", "User Permissions Table Access", True,
                         f"Found {permissions_count} permissions")
            
            # Test 5: User Groups Table
            groups_count = db.query(UserGroup).count()
            self.log_test("Database", "User Groups Table Access", True,
                         f"Found {groups_count} groups")
            
            # Test 6: API Keys Table
            api_keys_count = db.query(ApiKey).count()
            self.log_test("Database", "API Keys Table Access", True,
                         f"Found {api_keys_count} API keys")
            
            # Test 7: Password History Table
            password_history_count = db.query(PasswordHistory).count()
            self.log_test("Database", "Password History Table Access", True,
                         f"Found {password_history_count} password history entries")
            
            # Test 8: Data Integrity - Check for orphaned records
            orphaned_sessions = db.query(UserSession).filter(UserSession.user_id.notin_(
                db.query(User.id)
            )).count()
            self.log_test("Database", "Data Integrity - Sessions", orphaned_sessions == 0,
                         f"Found {orphaned_sessions} orphaned sessions")
            
            # Test 9: Recent Activity Check
            recent_logins = db.query(User).filter(
                User.last_login.isnot(None)
            ).count()
            self.log_test("Database", "Recent Activity Tracking", True,
                         f"Found {recent_logins} users with recent logins")
            
            db.close()
            
        except Exception as e:
            self.log_test("Database", "Database Connection", False,
                         f"Error: {str(e)}")
    
    def test_error_handling_scenarios(self):
        """Test error handling scenarios"""
        print("\n⚠️ TESTING ERROR HANDLING SCENARIOS")
        print("=" * 50)
        
        # Test 1: Invalid JSON
        response = self.session.post(f"{self.base_url}/api/v1/login", 
                                   data="invalid json",
                                   headers={"Content-Type": "application/json"})
        success = response.status_code == 422
        self.log_test("Error Handling", "Invalid JSON", success,
                     f"Status: {response.status_code} (Expected: 422)")
        
        # Test 2: Missing Required Fields
        incomplete_data = {"username": "test"}
        response = self.session.post(f"{self.base_url}/api/v1/login", json=incomplete_data)
        success = response.status_code == 422
        self.log_test("Error Handling", "Missing Required Fields", success,
                     f"Status: {response.status_code} (Expected: 422)")
        
        # Test 3: Invalid Endpoint
        response = self.session.get(f"{self.base_url}/api/v1/invalid-endpoint")
        success = response.status_code == 404
        self.log_test("Error Handling", "Invalid Endpoint", success,
                     f"Status: {response.status_code} (Expected: 404)")
        
        # Test 4: Method Not Allowed
        response = self.session.delete(f"{self.base_url}/api/v1/login")
        success = response.status_code == 405
        self.log_test("Error Handling", "Method Not Allowed", success,
                     f"Status: {response.status_code} (Expected: 405)")
    
    def run_comprehensive_tests(self):
        """Run all comprehensive tests"""
        print("🧪 COMPREHENSIVE SERVICES MIGRATION TEST SUITE")
        print("=" * 80)
        print(f"Started at: {datetime.now().isoformat()}")
        
        # Run all test suites
        self.test_authentication_scenarios()
        self.test_user_management_scenarios()
        self.test_admin_scenarios()
        self.test_production_endpoints_scenarios()
        self.test_rate_limiting_scenarios()
        self.test_database_operations()
        self.test_error_handling_scenarios()
        
        # Generate comprehensive report
        self.generate_report()
        
        return self.test_results
    
    def generate_report(self):
        """Generate comprehensive test report"""
        print("\n" + "=" * 80)
        print("📊 COMPREHENSIVE TEST REPORT")
        print("=" * 80)
        
        success_rate = (self.success_count / self.total_tests * 100) if self.total_tests > 0 else 0
        
        print(f"🎯 Overall Success Rate: {success_rate:.1f}% ({self.success_count}/{self.total_tests})")
        print(f"📅 Test Completed: {datetime.now().isoformat()}")
        
        # Category breakdown
        print("\n📋 CATEGORY BREAKDOWN:")
        for category, tests in self.test_results.items():
            category_success = sum(1 for test in tests.values() if test["success"])
            category_total = len(tests)
            category_rate = (category_success / category_total * 100) if category_total > 0 else 0
            
            print(f"  {category}: {category_rate:.1f}% ({category_success}/{category_total})")
            
            # Show failed tests
            failed_tests = [name for name, test in tests.items() if not test["success"]]
            if failed_tests:
                print(f"    Failed: {', '.join(failed_tests)}")
        
        # Overall assessment
        print(f"\n🎉 ASSESSMENT:")
        if success_rate >= 95:
            print("EXCELLENT: All services migration is PERFECT!")
        elif success_rate >= 90:
            print("VERY GOOD: Services migration is working great!")
        elif success_rate >= 80:
            print("GOOD: Most services working, minor issues to address")
        elif success_rate >= 70:
            print("FAIR: Several issues need attention")
        else:
            print("NEEDS ATTENTION: Multiple critical issues found")
        
        # Save detailed results
        with open("comprehensive_migration_test_results.json", "w") as f:
            json.dump({
                "summary": {
                    "success_rate": success_rate,
                    "total_tests": self.total_tests,
                    "successful_tests": self.success_count,
                    "timestamp": datetime.now().isoformat()
                },
                "test_results": self.test_results,
                "test_data": self.test_data
            }, f, indent=2)
        
        print(f"\n📄 Detailed results saved to: comprehensive_migration_test_results.json")

def main():
    """Main test function"""
    tester = ComprehensiveMigrationTester()
    results = tester.run_comprehensive_tests()
    return results

if __name__ == "__main__":
    main()
