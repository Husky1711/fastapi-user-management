#!/usr/bin/env python3
"""
Comprehensive Auth Services Test Suite

Tests all auth services after migration to ensure they work correctly
"""

import requests
import json
import time
from typing import Dict, Any, Optional

class AuthServicesTester:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.session = requests.Session()
        self.auth_token = None
        self.refresh_token = None
        self.test_results = {}
    
    def test_basic_login(self) -> Dict[str, Any]:
        """Test basic login functionality"""
        print("\n🔐 Testing Basic Login...")
        results = {}
        
        try:
            login_data = {
                "username": "test_auth_user",
                "password": "testpass123"
            }
            response = self.session.post(f"{self.base_url}/api/v1/login", json=login_data)
            
            if response.status_code == 200:
                data = response.json()
                self.auth_token = data.get("access_token")
                self.refresh_token = data.get("refresh_token")
                
                results["login"] = "PASS"
                results["access_token"] = "PASS" if self.auth_token else "FAIL"
                results["refresh_token"] = "PASS" if self.refresh_token else "FAIL"
                results["token_type"] = "PASS" if data.get("token_type") == "bearer" else "FAIL"
                results["expires_in"] = "PASS" if data.get("expires_in") else "FAIL"
                
                print("✅ Basic login successful")
                print(f"✅ Access token: {self.auth_token[:20]}...")
                print(f"✅ Refresh token: {self.refresh_token[:20]}...")
                print(f"✅ Token type: {data.get('token_type')}")
                print(f"✅ Expires in: {data.get('expires_in')} seconds")
            else:
                results["login"] = f"FAIL: {response.status_code}"
                print(f"❌ Basic login failed: {response.status_code}")
                print(f"Response: {response.text}")
                
        except Exception as e:
            results["error"] = f"Basic login error: {str(e)}"
            print(f"❌ Basic login error: {e}")
        
        return results
    
    def test_enhanced_login_scenarios(self) -> Dict[str, Any]:
        """Test enhanced login with different session control strategies"""
        print("\n🚀 Testing Enhanced Login Scenarios...")
        results = {}
        
        strategies = [
            "allow_multiple",
            "replace_all", 
            "replace_same_device",
            "deny_if_exists",
            "limit_sessions"
        ]
        
        for strategy in strategies:
            try:
                login_data = {
                    "username": "test_auth_user",
                    "password": "testpass123"
                }
                response = self.session.post(f"{self.base_url}/api/v1/login-with-session-control?session_strategy={strategy}", json=login_data)
                
                if response.status_code == 200:
                    data = response.json()
                    results[f"enhanced_login_{strategy}"] = "PASS"
                    print(f"✅ Enhanced login ({strategy}): PASS")
                else:
                    results[f"enhanced_login_{strategy}"] = f"FAIL: {response.status_code}"
                    print(f"❌ Enhanced login ({strategy}): FAIL - {response.status_code}")
                    
            except Exception as e:
                results[f"enhanced_login_{strategy}_error"] = f"Error: {str(e)}"
                print(f"❌ Enhanced login ({strategy}) error: {e}")
        
        return results
    
    def test_refresh_token(self) -> Dict[str, Any]:
        """Test refresh token functionality"""
        print("\n🔄 Testing Refresh Token...")
        results = {}
        
        try:
            if not self.refresh_token:
                results["refresh_token"] = "FAIL: No refresh token available"
                print("❌ No refresh token available for testing")
                return results
            
            refresh_data = {"refresh_token": self.refresh_token}
            response = self.session.post(f"{self.base_url}/api/v1/refresh", json=refresh_data)
            
            if response.status_code == 200:
                data = response.json()
                new_access_token = data.get("access_token")
                new_refresh_token = data.get("refresh_token")
                
                results["refresh_token"] = "PASS"
                results["new_access_token"] = "PASS" if new_access_token else "FAIL"
                results["new_refresh_token"] = "PASS" if new_refresh_token else "FAIL"
                
                # Update tokens for further tests
                self.auth_token = new_access_token
                self.refresh_token = new_refresh_token
                
                print("✅ Token refresh successful")
                print(f"✅ New access token: {new_access_token[:20]}...")
                print(f"✅ New refresh token: {new_refresh_token[:20]}...")
            else:
                results["refresh_token"] = f"FAIL: {response.status_code}"
                print(f"❌ Token refresh failed: {response.status_code}")
                print(f"Response: {response.text}")
                
        except Exception as e:
            results["refresh_error"] = f"Error: {str(e)}"
            print(f"❌ Refresh token error: {e}")
        
        return results
    
    def test_logout_scenarios(self) -> Dict[str, Any]:
        """Test logout functionality"""
        print("\n🚪 Testing Logout Scenarios...")
        results = {}
        
        try:
            if not self.refresh_token:
                results["logout"] = "FAIL: No refresh token available"
                print("❌ No refresh token available for logout test")
                return results
            
            # Test single logout
            logout_data = {"refresh_token": self.refresh_token}
            response = self.session.post(f"{self.base_url}/api/v1/logout", json=logout_data)
            
            if response.status_code == 200:
                data = response.json()
                results["single_logout"] = "PASS"
                print("✅ Single logout successful")
                print(f"✅ Logout message: {data.get('message', 'No message')}")
            else:
                results["single_logout"] = f"FAIL: {response.status_code}"
                print(f"❌ Single logout failed: {response.status_code}")
            
            # Re-login for logout-all test
            login_data = {
                "username": "test_auth_user",
                "password": "testpass123"
            }
            response = self.session.post(f"{self.base_url}/api/v1/login", json=login_data)
            
            if response.status_code == 200:
                data = response.json()
                self.auth_token = data.get("access_token")
                self.refresh_token = data.get("refresh_token")
                
                # Test logout all
                logout_all_headers = {"Authorization": f"Bearer {self.auth_token}"}
                response = self.session.post(f"{self.base_url}/api/v1/logout-all", headers=logout_all_headers)
                
                if response.status_code == 200:
                    data = response.json()
                    results["logout_all"] = "PASS"
                    print("✅ Logout all successful")
                    print(f"✅ Logout all message: {data.get('message', 'No message')}")
                else:
                    results["logout_all"] = f"FAIL: {response.status_code}"
                    print(f"❌ Logout all failed: {response.status_code}")
            else:
                results["re_login_for_logout_all"] = f"FAIL: {response.status_code}"
                print(f"❌ Re-login for logout-all failed: {response.status_code}")
                
        except Exception as e:
            results["logout_error"] = f"Error: {str(e)}"
            print(f"❌ Logout error: {e}")
        
        return results
    
    def test_authenticated_endpoints(self) -> Dict[str, Any]:
        """Test endpoints that require authentication"""
        print("\n🔒 Testing Authenticated Endpoints...")
        results = {}
        
        try:
            # Re-login to get fresh token
            login_data = {
                "username": "test_auth_user",
                "password": "testpass123"
            }
            response = self.session.post(f"{self.base_url}/api/v1/login", json=login_data)
            
            if response.status_code != 200:
                results["re_login"] = f"FAIL: {response.status_code}"
                print("❌ Re-login failed for authenticated endpoint tests")
                return results
            
            data = response.json()
            self.auth_token = data.get("access_token")
            headers = {"Authorization": f"Bearer {self.auth_token}"}
            
            # Test profile endpoint
            response = self.session.get(f"{self.base_url}/api/v1/profile", headers=headers)
            if response.status_code == 200:
                results["profile"] = "PASS"
                print("✅ Profile endpoint successful")
            else:
                results["profile"] = f"FAIL: {response.status_code}"
                print(f"❌ Profile endpoint failed: {response.status_code}")
            
            # Test users endpoint
            response = self.session.get(f"{self.base_url}/api/v1/users", headers=headers)
            if response.status_code == 200:
                results["users"] = "PASS"
                print("✅ Users endpoint successful")
            else:
                results["users"] = f"FAIL: {response.status_code}"
                print(f"❌ Users endpoint failed: {response.status_code}")
            
            # Test sessions endpoint
            response = self.session.get(f"{self.base_url}/api/v1/sessions", headers=headers)
            if response.status_code == 200:
                results["sessions"] = "PASS"
                print("✅ Sessions endpoint successful")
            else:
                results["sessions"] = f"FAIL: {response.status_code}"
                print(f"❌ Sessions endpoint failed: {response.status_code}")
                
        except Exception as e:
            results["authenticated_error"] = f"Error: {str(e)}"
            print(f"❌ Authenticated endpoints error: {e}")
        
        return results
    
    def test_error_scenarios(self) -> Dict[str, Any]:
        """Test error scenarios"""
        print("\n⚠️ Testing Error Scenarios...")
        results = {}
        
        try:
            # Test invalid credentials
            login_data = {
                "username": "test_auth_user",
                "password": "wrongpassword"
            }
            response = self.session.post(f"{self.base_url}/api/v1/login", json=login_data)
            
            if response.status_code == 401:
                results["invalid_credentials"] = "PASS"
                print("✅ Invalid credentials correctly rejected (401)")
            else:
                results["invalid_credentials"] = f"FAIL: Expected 401, got {response.status_code}"
                print(f"❌ Invalid credentials test failed: Expected 401, got {response.status_code}")
            
            # Test invalid refresh token
            refresh_data = {"refresh_token": "invalid_token"}
            response = self.session.post(f"{self.base_url}/api/v1/refresh", json=refresh_data)
            
            if response.status_code == 401:
                results["invalid_refresh_token"] = "PASS"
                print("✅ Invalid refresh token correctly rejected (401)")
            else:
                results["invalid_refresh_token"] = f"FAIL: Expected 401, got {response.status_code}"
                print(f"❌ Invalid refresh token test failed: Expected 401, got {response.status_code}")
            
            # Test unauthorized access
            headers = {"Authorization": "Bearer invalid_token"}
            response = self.session.get(f"{self.base_url}/api/v1/profile", headers=headers)
            
            if response.status_code == 401:
                results["unauthorized_access"] = "PASS"
                print("✅ Unauthorized access correctly rejected (401)")
            else:
                results["unauthorized_access"] = f"FAIL: Expected 401, got {response.status_code}"
                print(f"❌ Unauthorized access test failed: Expected 401, got {response.status_code}")
                
        except Exception as e:
            results["error_scenarios_error"] = f"Error: {str(e)}"
            print(f"❌ Error scenarios test error: {e}")
        
        return results
    
    def run_all_tests(self) -> Dict[str, Any]:
        """Run all auth service tests"""
        print("🧪 Starting Comprehensive Auth Services Tests...")
        print("=" * 70)
        
        # Run all test suites
        self.test_results["basic_login"] = self.test_basic_login()
        self.test_results["enhanced_login"] = self.test_enhanced_login_scenarios()
        self.test_results["refresh_token"] = self.test_refresh_token()
        self.test_results["logout_scenarios"] = self.test_logout_scenarios()
        self.test_results["authenticated_endpoints"] = self.test_authenticated_endpoints()
        self.test_results["error_scenarios"] = self.test_error_scenarios()
        
        # Summary
        print("\n" + "=" * 70)
        print("📊 AUTH SERVICES TEST SUMMARY")
        print("=" * 70)
        
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
            print("🎉 EXCELLENT: All auth services are working perfectly!")
        elif success_rate >= 70:
            print("⚠️  GOOD: Most auth services are working, some issues to investigate")
        else:
            print("🚨 CRITICAL: Multiple auth services have issues, needs immediate attention")
        
        return self.test_results

def main():
    """Main test function"""
    tester = AuthServicesTester()
    results = tester.run_all_tests()
    
    # Save results to file
    with open("auth_test_results.json", "w") as f:
        json.dump(results, f, indent=2)
    
    print(f"\n📄 Auth test results saved to: auth_test_results.json")
    return results

if __name__ == "__main__":
    main()
