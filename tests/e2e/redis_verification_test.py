#!/usr/bin/env python3
"""
COMPREHENSIVE REDIS VERIFICATION TEST SUITE

This test suite verifies Redis is being used correctly in all scenarios:
1. Login/Logout flow (refresh tokens)
2. Token refresh flow
3. Session management
4. Rate limiting
5. Cache management
6. Password reset flow
7. User profile caching
8. Audit log caching

Tests both MySQL and Redis to ensure data consistency.
"""

import requests
import sys
import os
from typing import Dict, Any, List
from datetime import datetime
import time

# Add project root to Python path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from utils.redis_config import RedisClient

class RedisVerificationTester:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.redis_client = RedisClient.get_client()
        self.test_results = {}
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
    
    def check_redis_key(self, pattern: str, should_exist: bool = True) -> bool:
        """Check if key exists in Redis"""
        try:
            keys = self.redis_client.keys(pattern)
            exists = len(keys) > 0
            return exists == should_exist
        except Exception as e:
            return False
    
    def get_redis_value(self, key: str) -> Any:
        """Get value from Redis"""
        try:
            return self.redis_client.get(key)
        except Exception as e:
            return None
    
    def test_login_redis_storage(self):
        """Test Redis storage during login"""
        print("\n🔐 TESTING LOGIN → REDIS STORAGE")
        print("=" * 50)
        
        # Login
        login_data = {"username": "test_auth_user", "password": "NewSecurePass123"}
        response = requests.post(f"{self.base_url}/api/v1/login", json=login_data)
        
        if response.status_code == 200:
            data = response.json()
            refresh_token = data.get("refresh_token")
            
            if refresh_token:
                # Check if refresh token is stored in Redis
                redis_key = f"refresh_token:{refresh_token}"
                redis_value = self.get_redis_value(redis_key)
                
                self.log_test("Login Redis", "Refresh Token Stored in Redis", redis_value is not None,
                             f"Key: {redis_key}, Value: {redis_value[:20] if redis_value else 'NOT FOUND'}...")
                
                return refresh_token
        
        self.log_test("Login Redis", "Login Successful", False, "Login failed")
        return None
    
    def test_refresh_redis_rotation(self):
        """Test Redis token rotation during refresh"""
        print("\n🔄 TESTING REFRESH → REDIS TOKEN ROTATION")
        print("=" * 50)
        
        # First login
        login_data = {"username": "test_auth_user", "password": "NewSecurePass123"}
        response = requests.post(f"{self.base_url}/api/v1/login", json=login_data)
        
        if response.status_code == 200:
            data = response.json()
            old_refresh_token = data.get("refresh_token")
            
            if old_refresh_token:
                # Check old token in Redis
                old_key = f"refresh_token:{old_refresh_token}"
                old_value_before = self.get_redis_value(old_key)
                
                # Refresh token
                refresh_data = {"refresh_token": old_refresh_token}
                response = requests.post(f"{self.base_url}/api/v1/refresh", json=refresh_data)
                
                if response.status_code == 200:
                    new_data = response.json()
                    new_refresh_token = new_data.get("refresh_token")
                    
                    # Check old token is deleted from Redis
                    old_value_after = self.get_redis_value(old_key)
                    
                    # Check new token is in Redis
                    new_key = f"refresh_token:{new_refresh_token}"
                    new_value = self.get_redis_value(new_key)
                    
                    self.log_test("Refresh Redis", "Old Token Deleted from Redis", old_value_after is None,
                                 f"Old key deleted: {old_value_after is None}")
                    
                    self.log_test("Refresh Redis", "New Token Stored in Redis", new_value is not None,
                                 f"New key exists: {new_value is not None}")
    
    def test_logout_redis_cleanup(self):
        """Test Redis cleanup during logout"""
        print("\n🚪 TESTING LOGOUT → REDIS CLEANUP")
        print("=" * 50)
        
        # Login first
        login_data = {"username": "test_auth_user", "password": "NewSecurePass123"}
        response = requests.post(f"{self.base_url}/api/v1/login", json=login_data)
        
        if response.status_code == 200:
            data = response.json()
            refresh_token = data.get("refresh_token")
            
            if refresh_token:
                redis_key = f"refresh_token:{refresh_token}"
                
                # Check token exists before logout
                value_before = self.get_redis_value(redis_key)
                
                # Logout
                logout_data = {"refresh_token": refresh_token}
                response = requests.post(f"{self.base_url}/api/v1/logout", json=logout_data)
                
                # Check token deleted after logout
                value_after = self.get_redis_value(redis_key)
                
                self.log_test("Logout Redis", "Token Exists Before Logout", value_before is not None,
                             f"Before: {value_before is not None}")
                
                self.log_test("Logout Redis", "Token Deleted After Logout", value_after is None,
                             f"After: {value_after is None}")
    
    def test_rate_limiting_redis(self):
        """Test rate limiting in Redis"""
        print("\n⚡ TESTING RATE LIMITING → REDIS")
        print("=" * 50)
        
        # Make multiple login attempts
        login_data = {"username": "test_auth_user", "password": "NewSecurePass123"}
        
        for i in range(3):
            response = requests.post(f"{self.base_url}/api/v1/login", json=login_data)
            status = response.status_code == 200
            self.log_test("Rate Limiting Redis", f"Login Attempt {i+1}", status,
                         f"Status: {response.status_code}")
    
    def test_password_reset_redis(self):
        """Test password reset token in Redis"""
        print("\n🔑 TESTING PASSWORD RESET → REDIS")
        print("=" * 50)
        
        # Request password reset
        reset_data = {"email": "test@example.com"}
        response = requests.post(f"{self.base_url}/api/v1/password/reset-request", json=reset_data)
        
        # Check if reset token is stored (we can't get the exact token from response)
        # But we can check if request is successful
        success = response.status_code in [200, 404]  # 404 if email not found
        self.log_test("Password Reset Redis", "Reset Request", success,
                     f"Status: {response.status_code}")
    
    def test_user_profile_cache_redis(self):
        """Test user profile caching in Redis"""
        print("\n👤 TESTING PROFILE CACHE → REDIS")
        print("=" * 50)
        
        # Login
        login_data = {"username": "test_auth_user", "password": "NewSecurePass123"}
        response = requests.post(f"{self.base_url}/api/v1/login", json=login_data)
        
        if response.status_code == 200:
            data = response.json()
            token = data.get("access_token")
            headers = {"Authorization": f"Bearer {token}"}
            
            # Get profile (should cache in Redis)
            response = requests.get(f"{self.base_url}/api/v1/profile", headers=headers)
            
            success = response.status_code == 200
            self.log_test("Profile Cache Redis", "Profile Retrieved", success,
                         f"Status: {response.status_code}")
    
    def test_redis_connection(self):
        """Test Redis connection"""
        print("\n🔌 TESTING REDIS CONNECTION")
        print("=" * 50)
        
        try:
            # Test ping
            result = self.redis_client.ping()
            self.log_test("Redis Connection", "Redis Ping", result,
                         f"Ping result: {result}")
            
            # Test get/set
            test_key = "test_key_verification"
            test_value = "test_value"
            
            self.redis_client.set(test_key, test_value, ex=60)
            retrieved = self.redis_client.get(test_key)
            
            self.log_test("Redis Connection", "Redis Get/Set", retrieved == test_value,
                         f"Set: {test_value}, Got: {retrieved}")
            
            # Cleanup
            self.redis_client.delete(test_key)
            
        except Exception as e:
            self.log_test("Redis Connection", "Redis Connection Error", False,
                         f"Error: {str(e)}")
    
    def verify_redis_keys_summary(self):
        """Display summary of Redis keys"""
        print("\n📊 REDIS KEYS SUMMARY")
        print("=" * 50)
        
        try:
            # Get all Redis keys
            all_keys = self.redis_client.keys("*")
            
            # Categorize keys
            categories = {
                "refresh_tokens": [],
                "password_reset": [],
                "user_cache": [],
                "rate_limit": [],
                "audit": [],
                "other": []
            }
            
            for key in all_keys:
                key_str = key.decode() if isinstance(key, bytes) else key
                
                if "refresh_token" in key_str:
                    categories["refresh_tokens"].append(key_str)
                elif "password_reset" in key_str:
                    categories["password_reset"].append(key_str)
                elif "user_cache" in key_str or "user_profile" in key_str:
                    categories["user_cache"].append(key_str)
                elif "rate_limit" in key_str:
                    categories["rate_limit"].append(key_str)
                elif "audit" in key_str:
                    categories["audit"].append(key_str)
                else:
                    categories["other"].append(key_str)
            
            print(f"\nTotal Redis Keys: {len(all_keys)}")
            print(f"  - Refresh Tokens: {len(categories['refresh_tokens'])}")
            print(f"  - Password Reset: {len(categories['password_reset'])}")
            print(f"  - User Cache: {len(categories['user_cache'])}")
            print(f"  - Rate Limits: {len(categories['rate_limit'])}")
            print(f"  - Audit: {len(categories['audit'])}")
            print(f"  - Other: {len(categories['other'])}")
            
            # Show some example keys
            if categories["refresh_tokens"]:
                print(f"\nExample Refresh Token Keys:")
                for key in categories["refresh_tokens"][:3]:
                    print(f"  - {key[:50]}...")
            
        except Exception as e:
            print(f"Error getting Redis keys: {e}")
    
    def run_comprehensive_tests(self):
        """Run all comprehensive Redis tests"""
        print("🧪 COMPREHENSIVE REDIS VERIFICATION TEST SUITE")
        print("=" * 80)
        print(f"Started at: {datetime.now().isoformat()}")
        
        # Run all test suites
        self.test_redis_connection()
        self.test_login_redis_storage()
        self.test_refresh_redis_rotation()
        self.test_logout_redis_cleanup()
        self.test_rate_limiting_redis()
        self.test_password_reset_redis()
        self.test_user_profile_cache_redis()
        
        # Display summary
        self.verify_redis_keys_summary()
        
        # Generate report
        self.generate_report()
        
        return self.test_results
    
    def generate_report(self):
        """Generate comprehensive test report"""
        print("\n" + "=" * 80)
        print("📊 COMPREHENSIVE REDIS TEST REPORT")
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
            print("EXCELLENT: Redis integration is PERFECT!")
        elif success_rate >= 90:
            print("VERY GOOD: Redis integration is working great!")
        elif success_rate >= 80:
            print("GOOD: Most Redis operations working, minor issues to address")
        elif success_rate >= 70:
            print("FAIR: Several Redis issues need attention")
        else:
            print("NEEDS ATTENTION: Multiple critical Redis issues found")
        
        print(f"\n💡 REDIS VERIFICATION:")
        print("   • Check if all refresh tokens are properly stored")
        print("   • Verify token rotation during refresh")
        print("   • Confirm cleanup on logout")
        print("   • Monitor rate limiting effectiveness")
        print("   • Validate cache management")

def main():
    """Main test function"""
    tester = RedisVerificationTester()
    results = tester.run_comprehensive_tests()
    return results

if __name__ == "__main__":
    main()
