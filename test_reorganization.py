#!/usr/bin/env python3
"""
Services Reorganization Test Script

This script tests all API endpoints after each reorganization step
to ensure everything is working correctly.
"""

import requests
import json
import time
from typing import Dict, Any

class ReorganizationTester:
    def __init__(self, base_url: str = "http://localhost:9000"):
        self.base_url = base_url
        self.session = requests.Session()
        self.auth_token = None
        self.test_results = {}
    
    def test_server_health(self) -> bool:
        """Test if server is running"""
        try:
            response = self.session.get(f"{self.base_url}/health")
            if response.status_code == 200:
                print("✅ Server is running")
                return True
            else:
                print(f"❌ Server health check failed: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Server not accessible: {e}")
            return False
    
    def test_authentication(self) -> Dict[str, Any]:
        """Test authentication endpoints"""
        print("\n🔐 Testing Authentication APIs...")
        results = {}
        
        try:
            # Test login
            login_data = {
                "username": "test_fix_user",
                "password": "BrandNewPassword123"
            }
            response = self.session.post(f"{self.base_url}/api/v1/login", json=login_data)
            
            if response.status_code == 200:
                data = response.json()
                self.auth_token = data.get("access_token")
                results["login"] = "PASS"
                print("✅ Login successful")
            else:
                results["login"] = f"FAIL: {response.status_code}"
                print(f"❌ Login failed: {response.status_code}")
                return results
            
            # Test refresh token
            refresh_data = {"refresh_token": data.get("refresh_token")}
            response = self.session.post(f"{self.base_url}/api/v1/refresh", json=refresh_data)
            
            if response.status_code == 200:
                results["refresh"] = "PASS"
                print("✅ Token refresh successful")
            else:
                results["refresh"] = f"FAIL: {response.status_code}"
                print(f"❌ Token refresh failed: {response.status_code}")
            
            # Test logout
            logout_data = {"refresh_token": data.get("refresh_token")}
            response = self.session.post(f"{self.base_url}/api/v1/logout", json=logout_data)
            
            if response.status_code == 200:
                results["logout"] = "PASS"
                print("✅ Logout successful")
            else:
                results["logout"] = f"FAIL: {response.status_code}"
                print(f"❌ Logout failed: {response.status_code}")
                
        except Exception as e:
            results["error"] = f"Authentication test error: {str(e)}"
            print(f"❌ Authentication test error: {e}")
        
        return results
    
    def test_user_management(self) -> Dict[str, Any]:
        """Test user management endpoints"""
        print("\n👥 Testing User Management APIs...")
        results = {}
        
        try:
            # Re-login for authenticated tests
            login_data = {
                "username": "test_fix_user",
                "password": "BrandNewPassword123"
            }
            response = self.session.post(f"{self.base_url}/api/v1/login", json=login_data)
            
            if response.status_code != 200:
                results["login"] = f"FAIL: {response.status_code}"
                return results
            
            data = response.json()
            self.auth_token = data.get("access_token")
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
                
        except Exception as e:
            results["error"] = f"User management test error: {str(e)}"
            print(f"❌ User management test error: {e}")
        
        return results
    
    def test_production_endpoints(self) -> Dict[str, Any]:
        """Test production endpoints"""
        print("\n🏭 Testing Production APIs...")
        results = {}
        
        try:
            if not self.auth_token:
                # Re-login
                login_data = {
                    "username": "test_fix_user",
                    "password": "BrandNewPassword123"
                }
                response = self.session.post(f"{self.base_url}/api/v1/login", json=login_data)
                if response.status_code == 200:
                    data = response.json()
                    self.auth_token = data.get("access_token")
                else:
                    results["login"] = f"FAIL: {response.status_code}"
                    return results
            
            headers = {"Authorization": f"Bearer {self.auth_token}"}
            
            # Test audit logs
            response = self.session.get(f"{self.base_url}/api/v1/audit/logs", headers=headers)
            if response.status_code == 200:
                results["audit_logs"] = "PASS"
                print("✅ Audit logs successful")
            else:
                results["audit_logs"] = f"FAIL: {response.status_code}"
                print(f"❌ Audit logs failed: {response.status_code}")
            
            # Test sessions
            response = self.session.get(f"{self.base_url}/api/v1/sessions", headers=headers)
            if response.status_code == 200:
                results["sessions"] = "PASS"
                print("✅ Sessions successful")
            else:
                results["sessions"] = f"FAIL: {response.status_code}"
                print(f"❌ Sessions failed: {response.status_code}")
            
            # Test permissions
            response = self.session.get(f"{self.base_url}/api/v1/permissions", headers=headers)
            if response.status_code == 200:
                results["permissions"] = "PASS"
                print("✅ Permissions successful")
            else:
                results["permissions"] = f"FAIL: {response.status_code}"
                print(f"❌ Permissions failed: {response.status_code}")
            
            # Test groups
            response = self.session.get(f"{self.base_url}/api/v1/groups", headers=headers)
            if response.status_code == 200:
                results["groups"] = "PASS"
                print("✅ Groups successful")
            else:
                results["groups"] = f"FAIL: {response.status_code}"
                print(f"❌ Groups failed: {response.status_code}")
            
            # Test API keys
            response = self.session.get(f"{self.base_url}/api/v1/api-keys", headers=headers)
            if response.status_code == 200:
                results["api_keys"] = "PASS"
                print("✅ API keys successful")
            else:
                results["api_keys"] = f"FAIL: {response.status_code}"
                print(f"❌ API keys failed: {response.status_code}")
            
            # Test password history
            response = self.session.get(f"{self.base_url}/api/v1/password/history", headers=headers)
            if response.status_code == 200:
                results["password_history"] = "PASS"
                print("✅ Password history successful")
            else:
                results["password_history"] = f"FAIL: {response.status_code}"
                print(f"❌ Password history failed: {response.status_code}")
                
        except Exception as e:
            results["error"] = f"Production endpoints test error: {str(e)}"
            print(f"❌ Production endpoints test error: {e}")
        
        return results
    
    def run_all_tests(self) -> Dict[str, Any]:
        """Run all tests"""
        print("🧪 Starting Services Reorganization Tests...")
        print("=" * 60)
        
        # Test server health
        if not self.test_server_health():
            return {"error": "Server not accessible"}
        
        # Run all test suites
        self.test_results["authentication"] = self.test_authentication()
        self.test_results["user_management"] = self.test_user_management()
        self.test_results["production_endpoints"] = self.test_production_endpoints()
        
        # Summary
        print("\n" + "=" * 60)
        print("📊 TEST SUMMARY")
        print("=" * 60)
        
        total_tests = 0
        passed_tests = 0
        
        for category, tests in self.test_results.items():
            print(f"\n{category.upper()}:")
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
            print("🎉 EXCELLENT: All services are working correctly!")
        elif success_rate >= 70:
            print("⚠️  GOOD: Most services are working, some issues to investigate")
        else:
            print("🚨 CRITICAL: Multiple services have issues, needs immediate attention")
        
        return self.test_results

def main():
    """Main test function"""
    tester = ReorganizationTester()
    results = tester.run_all_tests()
    
    # Save results to file
    with open("test_results.json", "w") as f:
        json.dump(results, f, indent=2)
    
    print(f"\n📄 Test results saved to: test_results.json")
    return results

if __name__ == "__main__":
    main()
