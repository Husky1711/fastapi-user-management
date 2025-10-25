#!/usr/bin/env python3
"""
Comprehensive Test Suite for Auth + Users Services Migration

Tests all APIs after auth and users services migration to ensure everything works correctly
"""

import requests
import json
import time
from typing import Dict, Any, Optional

class AuthUsersMigrationTester:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.session = requests.Session()
        self.auth_token = None
        self.refresh_token = None
        self.test_results = {}
    
    def test_auth_apis(self) -> Dict[str, Any]:
        """Test all authentication APIs"""
        print("\n🔐 Testing Authentication APIs...")
        results = {}
        
        try:
            # Test basic login
            login_data = {
                "username": "test_auth_user",
                "password": "testpass123"
            }
            response = self.session.post(f"{self.base_url}/api/v1/login", json=login_data)
            
            if response.status_code == 200:
                data = response.json()
                self.auth_token = data.get("access_token")
                self.refresh_token = data.get("refresh_token")
                
                results["basic_login"] = "PASS"
                print("✅ Basic login successful")
            else:
                results["basic_login"] = f"FAIL: {response.status_code}"
                print(f"❌ Basic login failed: {response.status_code}")
                return results
            
            # Test enhanced login strategies
            strategies = ["allow_multiple", "replace_all", "replace_same_device", "limit_sessions"]
            for strategy in strategies:
                try:
                    response = self.session.post(f"{self.base_url}/api/v1/login-with-session-control?session_strategy={strategy}", json=login_data)
                    if response.status_code == 200:
                        results[f"enhanced_login_{strategy}"] = "PASS"
                        print(f"✅ Enhanced login ({strategy}): PASS")
                    else:
                        results[f"enhanced_login_{strategy}"] = f"FAIL: {response.status_code}"
                        print(f"❌ Enhanced login ({strategy}): FAIL - {response.status_code}")
                except Exception as e:
                    results[f"enhanced_login_{strategy}"] = f"ERROR: {str(e)}"
                    print(f"❌ Enhanced login ({strategy}): ERROR - {e}")
            
            # Test refresh token
            if self.refresh_token:
                refresh_data = {"refresh_token": self.refresh_token}
                response = self.session.post(f"{self.base_url}/api/v1/refresh", json=refresh_data)
                
                if response.status_code == 200:
                    data = response.json()
                    self.auth_token = data.get("access_token")
                    self.refresh_token = data.get("refresh_token")
                    results["refresh_token"] = "PASS"
                    print("✅ Token refresh successful")
                else:
                    results["refresh_token"] = f"FAIL: {response.status_code}"
                    print(f"❌ Token refresh failed: {response.status_code}")
            
            # Test logout
            if self.refresh_token:
                logout_data = {"refresh_token": self.refresh_token}
                response = self.session.post(f"{self.base_url}/api/v1/logout", json=logout_data)
                
                if response.status_code == 200:
                    results["logout"] = "PASS"
                    print("✅ Logout successful")
                else:
                    results["logout"] = f"FAIL: {response.status_code}"
                    print(f"❌ Logout failed: {response.status_code}")
            
            # Re-login for further tests
            response = self.session.post(f"{self.base_url}/api/v1/login", json=login_data)
            if response.status_code == 200:
                data = response.json()
                self.auth_token = data.get("access_token")
                self.refresh_token = data.get("refresh_token")
                
        except Exception as e:
            results["auth_error"] = f"Error: {str(e)}"
            print(f"❌ Auth APIs error: {e}")
        
        return results
    
    def test_user_management_apis(self) -> Dict[str, Any]:
        """Test all user management APIs"""
        print("\n👥 Testing User Management APIs...")
        results = {}
        
        try:
            if not self.auth_token:
                # Re-login
                login_data = {
                    "username": "test_auth_user",
                    "password": "testpass123"
                }
                response = self.session.post(f"{self.base_url}/api/v1/login", json=login_data)
                if response.status_code == 200:
                    data = response.json()
                    self.auth_token = data.get("access_token")
                else:
                    results["re_login"] = f"FAIL: {response.status_code}"
                    return results
            
            headers = {"Authorization": f"Bearer {self.auth_token}"}
            
            # Test get users
            response = self.session.get(f"{self.base_url}/api/v1/users", headers=headers)
            if response.status_code == 200:
                results["get_users"] = "PASS"
                print("✅ Get users successful")
            else:
                results["get_users"] = f"FAIL: {response.status_code}"
                print(f"❌ Get users failed: {response.status_code}")
            
            # Test get user profile
            response = self.session.get(f"{self.base_url}/api/v1/profile", headers=headers)
            if response.status_code == 200:
                results["get_profile"] = "PASS"
                print("✅ Get profile successful")
            else:
                results["get_profile"] = f"FAIL: {response.status_code}"
                print(f"❌ Get profile failed: {response.status_code}")
            
            # Test update profile
            profile_data = {
                "email": "updated_test@example.com",
                "phone_number": "1234567890"
            }
            response = self.session.put(f"{self.base_url}/api/v1/profile", json=profile_data, headers=headers)
            if response.status_code == 200:
                results["update_profile"] = "PASS"
                print("✅ Update profile successful")
            else:
                results["update_profile"] = f"FAIL: {response.status_code}"
                print(f"❌ Update profile failed: {response.status_code}")
            
            # Test password change
            password_data = {
                "current_password": "testpass123",
                "new_password": "newtestpass123"
            }
            response = self.session.post(f"{self.base_url}/api/v1/password/change", json=password_data, headers=headers)
            if response.status_code == 200:
                results["password_change"] = "PASS"
                print("✅ Password change successful")
                
                # Update password for further tests
                password_data = {
                    "current_password": "newtestpass123",
                    "new_password": "testpass123"
                }
                response = self.session.post(f"{self.base_url}/api/v1/password/change", json=password_data, headers=headers)
                if response.status_code == 200:
                    print("✅ Password reverted successfully")
                else:
                    print(f"⚠️ Password revert failed: {response.status_code}")
            else:
                results["password_change"] = f"FAIL: {response.status_code}"
                print(f"❌ Password change failed: {response.status_code}")
            
            # Test password history
            response = self.session.get(f"{self.base_url}/api/v1/password/history", headers=headers)
            if response.status_code == 200:
                results["password_history"] = "PASS"
                print("✅ Password history successful")
            else:
                results["password_history"] = f"FAIL: {response.status_code}"
                print(f"❌ Password history failed: {response.status_code}")
                
        except Exception as e:
            results["user_management_error"] = f"Error: {str(e)}"
            print(f"❌ User management APIs error: {e}")
        
        return results
    
    def test_password_reset_apis(self) -> Dict[str, Any]:
        """Test password reset APIs"""
        print("\n🔑 Testing Password Reset APIs...")
        results = {}
        
        try:
            # Test password reset request
            reset_data = {
                "email": "test@example.com"
            }
            response = self.session.post(f"{self.base_url}/api/v1/password/reset/request", json=reset_data)
            if response.status_code == 200:
                results["password_reset_request"] = "PASS"
                print("✅ Password reset request successful")
            else:
                results["password_reset_request"] = f"FAIL: {response.status_code}"
                print(f"❌ Password reset request failed: {response.status_code}")
            
            # Test password reset validation (with invalid token)
            validation_data = {
                "token": "invalid_token",
                "password": "newpassword123"
            }
            response = self.session.post(f"{self.base_url}/api/v1/password/reset/confirm", json=validation_data)
            if response.status_code == 400:  # Expected to fail with invalid token
                results["password_reset_validation"] = "PASS"
                print("✅ Password reset validation correctly rejected invalid token")
            else:
                results["password_reset_validation"] = f"FAIL: Expected 400, got {response.status_code}"
                print(f"❌ Password reset validation test failed: Expected 400, got {response.status_code}")
                
        except Exception as e:
            results["password_reset_error"] = f"Error: {str(e)}"
            print(f"❌ Password reset APIs error: {e}")
        
        return results
    
    def test_admin_user_creation(self) -> Dict[str, Any]:
        """Test admin user creation APIs"""
        print("\n👨‍💼 Testing Admin User Creation APIs...")
        results = {}
        
        try:
            if not self.auth_token:
                # Re-login
                login_data = {
                    "username": "test_auth_user",
                    "password": "testpass123"
                }
                response = self.session.post(f"{self.base_url}/api/v1/login", json=login_data)
                if response.status_code == 200:
                    data = response.json()
                    self.auth_token = data.get("access_token")
                else:
                    results["re_login"] = f"FAIL: {response.status_code}"
                    return results
            
            headers = {"Authorization": f"Bearer {self.auth_token}"}
            
            # Test admin create user
            user_data = {
                "username": f"test_user_{int(time.time())}",
                "email": f"test_{int(time.time())}@example.com",
                "role": "user",
                "phone_number": "1234567890"
            }
            response = self.session.post(f"{self.base_url}/api/v1/admin/users/create", json=user_data, headers=headers)
            if response.status_code == 200:
                results["admin_create_user"] = "PASS"
                print("✅ Admin create user successful")
            else:
                results["admin_create_user"] = f"FAIL: {response.status_code}"
                print(f"❌ Admin create user failed: {response.status_code}")
                
        except Exception as e:
            results["admin_user_creation_error"] = f"Error: {str(e)}"
            print(f"❌ Admin user creation APIs error: {e}")
        
        return results
    
    def test_production_endpoints(self) -> Dict[str, Any]:
        """Test production endpoints"""
        print("\n🏭 Testing Production Endpoints...")
        results = {}
        
        try:
            if not self.auth_token:
                # Re-login
                login_data = {
                    "username": "test_auth_user",
                    "password": "testpass123"
                }
                response = self.session.post(f"{self.base_url}/api/v1/login", json=login_data)
                if response.status_code == 200:
                    data = response.json()
                    self.auth_token = data.get("access_token")
                else:
                    results["re_login"] = f"FAIL: {response.status_code}"
                    return results
            
            headers = {"Authorization": f"Bearer {self.auth_token}"}
            
            # Test sessions
            response = self.session.get(f"{self.base_url}/api/v1/sessions", headers=headers)
            if response.status_code == 200:
                results["sessions"] = "PASS"
                print("✅ Sessions endpoint successful")
            else:
                results["sessions"] = f"FAIL: {response.status_code}"
                print(f"❌ Sessions endpoint failed: {response.status_code}")
            
            # Test audit logs
            response = self.session.get(f"{self.base_url}/api/v1/audit/logs", headers=headers)
            if response.status_code == 200:
                results["audit_logs"] = "PASS"
                print("✅ Audit logs endpoint successful")
            else:
                results["audit_logs"] = f"FAIL: {response.status_code}"
                print(f"❌ Audit logs endpoint failed: {response.status_code}")
            
            # Test permissions
            response = self.session.get(f"{self.base_url}/api/v1/permissions", headers=headers)
            if response.status_code == 200:
                results["permissions"] = "PASS"
                print("✅ Permissions endpoint successful")
            else:
                results["permissions"] = f"FAIL: {response.status_code}"
                print(f"❌ Permissions endpoint failed: {response.status_code}")
            
            # Test groups
            response = self.session.get(f"{self.base_url}/api/v1/groups", headers=headers)
            if response.status_code == 200:
                results["groups"] = "PASS"
                print("✅ Groups endpoint successful")
            else:
                results["groups"] = f"FAIL: {response.status_code}"
                print(f"❌ Groups endpoint failed: {response.status_code}")
            
            # Test API keys
            response = self.session.get(f"{self.base_url}/api/v1/api-keys", headers=headers)
            if response.status_code == 200:
                results["api_keys"] = "PASS"
                print("✅ API keys endpoint successful")
            else:
                results["api_keys"] = f"FAIL: {response.status_code}"
                print(f"❌ API keys endpoint failed: {response.status_code}")
                
        except Exception as e:
            results["production_endpoints_error"] = f"Error: {str(e)}"
            print(f"❌ Production endpoints error: {e}")
        
        return results
    
    def run_all_tests(self) -> Dict[str, Any]:
        """Run all tests"""
        print("🧪 Starting Comprehensive Auth + Users Migration Tests...")
        print("=" * 80)
        
        # Run all test suites
        self.test_results["auth_apis"] = self.test_auth_apis()
        self.test_results["user_management_apis"] = self.test_user_management_apis()
        self.test_results["password_reset_apis"] = self.test_password_reset_apis()
        self.test_results["admin_user_creation"] = self.test_admin_user_creation()
        self.test_results["production_endpoints"] = self.test_production_endpoints()
        
        # Summary
        print("\n" + "=" * 80)
        print("📊 AUTH + USERS MIGRATION TEST SUMMARY")
        print("=" * 80)
        
        total_tests = 0
        passed_tests = 0
        
        for category, tests in self.test_results.items():
            print(f"\n{category.upper().replace('_', ' ')}:")
            for test_name, result in tests.items():
                total_tests += 1
                if result == "PASS":
                    passed_tests += 1
                    print(f"  ✅ {test_name}: PASS")
                else:
                    print(f"  ❌ {test_name}: {result}")
        
        success_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0
        print(f"\n🎯 Overall Success Rate: {success_rate:.1f}% ({passed_tests}/{total_tests})")
        
        if success_rate >= 90:
            print("🎉 EXCELLENT: Auth and Users services migration is perfect!")
        elif success_rate >= 70:
            print("⚠️  GOOD: Most services are working, some issues to investigate")
        else:
            print("🚨 CRITICAL: Multiple services have issues, needs immediate attention")
        
        return self.test_results

def main():
    """Main test function"""
    tester = AuthUsersMigrationTester()
    results = tester.run_all_tests()
    
    # Save results to file
    with open("auth_users_migration_test_results.json", "w") as f:
        json.dump(results, f, indent=2)
    
    print(f"\n📄 Test results saved to: auth_users_migration_test_results.json")
    return results

if __name__ == "__main__":
    main()
