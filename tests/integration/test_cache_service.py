"""
Comprehensive Test Suite for Cache Service
Tests all caching scenarios including profiles, sessions, permissions, and audit logs
"""

import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import asyncio
from datetime import datetime
from services.core.cache_service import cache_service

class CacheServiceTester:
    """Comprehensive cache service tester"""
    
    def __init__(self):
        self.test_results = []
        self.total_tests = 0
        self.passed_tests = 0
    
    def log_test(self, category: str, test_name: str, passed: bool, details: str = ""):
        """Log test result"""
        self.total_tests += 1
        if passed:
            self.passed_tests += 1
        
        status = "✅ PASS" if passed else "❌ FAIL"
        result = {
            "category": category,
            "test": test_name,
            "passed": passed,
            "details": details
        }
        self.test_results.append(result)
        
        print(f"  {status} - {category} > {test_name}")
        if details:
            print(f"      {details}")
    
    # ==================== PROFILE CACHE TESTS ====================
    
    def test_profile_cache_set_get(self):
        """Test setting and getting user profile from cache"""
        print("\n📋 PROFILE CACHE: Set & Get")
        print("=" * 50)
        
        user_id = 1
        test_profile = {
            "id": user_id,
            "username": "testuser",
            "email": "test@example.com",
            "role": "user",
            "organization_id": 1
        }
        
        # Set profile
        set_result = cache_service.set_user_profile(user_id, test_profile)
        self.log_test("Profile Cache", "Set Profile", set_result,
                     f"Set profile for user_id: {user_id}")
        
        # Get profile
        cached_profile = cache_service.get_user_profile(user_id)
        is_valid = cached_profile is not None and cached_profile["id"] == user_id
        self.log_test("Profile Cache", "Get Profile", is_valid,
                     f"Retrieved profile: {cached_profile.get('username') if cached_profile else 'None'}")
        
        # Verify data integrity
        if cached_profile:
            data_match = cached_profile["username"] == test_profile["username"]
            self.log_test("Profile Cache", "Data Integrity", data_match,
                         f"Username match: {cached_profile['username']} == {test_profile['username']}")
    
    def test_profile_cache_invalidation(self):
        """Test profile cache invalidation"""
        print("\n📋 PROFILE CACHE: Invalidation")
        print("=" * 50)
        
        user_id = 99
        test_profile = {
            "id": user_id,
            "username": "testuser99",
            "email": "test99@example.com"
        }
        
        # Set profile
        cache_service.set_user_profile(user_id, test_profile)
        
        # Verify it's cached
        cached_before = cache_service.get_user_profile(user_id)
        self.log_test("Profile Cache", "Pre-invalidation Check", cached_before is not None,
                     f"Cached before invalidation: {cached_before is not None}")
        
        # Invalidate
        invalidate_result = cache_service.invalidate_user_profile(user_id)
        self.log_test("Profile Cache", "Invalidate Command", invalidate_result,
                     f"Invalidation result: {invalidate_result}")
        
        # Verify it's gone
        cached_after = cache_service.get_user_profile(user_id)
        self.log_test("Profile Cache", "Post-invalidation Check", cached_after is None,
                     f"Cached after invalidation: {cached_after is not None}")
    
    def test_profile_cache_multiple_users(self):
        """Test caching multiple user profiles"""
        print("\n📋 PROFILE CACHE: Multiple Users")
        print("=" * 50)
        
        users = []
        for i in range(1, 6):
            user_data = {
                "id": i,
                "username": f"user{i}",
                "email": f"user{i}@example.com"
            }
            users.append((i, user_data))
            cache_service.set_user_profile(i, user_data)
        
        # Verify all cached
        all_cached = True
        for user_id, user_data in users:
            cached = cache_service.get_user_profile(user_id)
            if not cached or cached["username"] != user_data["username"]:
                all_cached = False
                break
        
        self.log_test("Profile Cache", "Multiple Users", all_cached,
                     f"Cached and verified {len(users)} user profiles")
    
    # ==================== SESSION CACHE TESTS ====================
    
    def test_session_cache_set_get(self):
        """Test setting and getting user sessions from cache"""
        print("\n📋 SESSION CACHE: Set & Get")
        print("=" * 50)
        
        user_id = 1
        test_sessions = [
            {
                "session_id": "sess1",
                "device_info": "Chrome on Windows",
                "ip_address": "192.168.1.1",
                "created_at": str(datetime.now())
            },
            {
                "session_id": "sess2",
                "device_info": "Mobile App",
                "ip_address": "192.168.1.2",
                "created_at": str(datetime.now())
            }
        ]
        
        # Set sessions
        set_result = cache_service.set_user_sessions(user_id, test_sessions)
        self.log_test("Session Cache", "Set Sessions", set_result,
                     f"Set {len(test_sessions)} sessions for user_id: {user_id}")
        
        # Get sessions
        cached_sessions = cache_service.get_user_sessions(user_id)
        is_valid = cached_sessions is not None and len(cached_sessions) == len(test_sessions)
        self.log_test("Session Cache", "Get Sessions", is_valid,
                     f"Retrieved {len(cached_sessions) if cached_sessions else 0} sessions")
        
        # Verify data integrity
        if cached_sessions:
            data_match = cached_sessions[0]["session_id"] == test_sessions[0]["session_id"]
            self.log_test("Session Cache", "Data Integrity", data_match,
                         f"Session ID match: {cached_sessions[0]['session_id']}")
    
    def test_session_cache_invalidation(self):
        """Test session cache invalidation"""
        print("\n📋 SESSION CACHE: Invalidation")
        print("=" * 50)
        
        user_id = 99
        test_sessions = [{"session_id": "sess99"}]
        
        cache_service.set_user_sessions(user_id, test_sessions)
        
        # Verify it's cached
        cached_before = cache_service.get_user_sessions(user_id)
        self.log_test("Session Cache", "Pre-invalidation Check", cached_before is not None,
                     f"Cached before invalidation: {cached_before is not None}")
        
        # Invalidate
        cache_service.invalidate_user_sessions(user_id)
        
        # Verify it's gone
        cached_after = cache_service.get_user_sessions(user_id)
        self.log_test("Session Cache", "Post-invalidation Check", cached_after is None,
                     f"Cached after invalidation: {cached_after is not None}")
    
    # ==================== PERMISSION CACHE TESTS ====================
    
    def test_permission_cache_set_get(self):
        """Test setting and getting user permissions from cache"""
        print("\n📋 PERMISSION CACHE: Set & Get")
        print("=" * 50)
        
        user_id = 1
        test_permissions = [
            {"resource": "users", "action": "read"},
            {"resource": "posts", "action": "write"},
            {"resource": "comments", "action": "delete"}
        ]
        
        # Set permissions
        set_result = cache_service.set_user_permissions(user_id, test_permissions)
        self.log_test("Permission Cache", "Set Permissions", set_result,
                     f"Set {len(test_permissions)} permissions for user_id: {user_id}")
        
        # Get permissions
        cached_permissions = cache_service.get_user_permissions(user_id)
        is_valid = cached_permissions is not None and len(cached_permissions) == len(test_permissions)
        self.log_test("Permission Cache", "Get Permissions", is_valid,
                     f"Retrieved {len(cached_permissions) if cached_permissions else 0} permissions")
        
        # Verify data integrity
        if cached_permissions:
            data_match = cached_permissions[0]["resource"] == test_permissions[0]["resource"]
            self.log_test("Permission Cache", "Data Integrity", data_match,
                         f"Permission match: {cached_permissions[0]['resource']}")
    
    def test_permission_cache_invalidation(self):
        """Test permission cache invalidation"""
        print("\n📋 PERMISSION CACHE: Invalidation")
        print("=" * 50)
        
        user_id = 99
        test_permissions = [{"resource": "test", "action": "read"}]
        
        cache_service.set_user_permissions(user_id, test_permissions)
        
        # Invalidate
        cache_service.invalidate_user_permissions(user_id)
        
        # Verify it's gone
        cached_after = cache_service.get_user_permissions(user_id)
        self.log_test("Permission Cache", "Post-invalidation Check", cached_after is None,
                     f"Cached after invalidation: {cached_after is not None}")
    
    # ==================== AUDIT LOG CACHE TESTS ====================
    
    def test_audit_log_cache_set_get(self):
        """Test setting and getting audit logs from cache"""
        print("\n📋 AUDIT LOG CACHE: Set & Get")
        print("=" * 50)
        
        user_id = 1
        test_logs = [
            {
                "id": 1,
                "action": "login",
                "timestamp": str(datetime.now()),
                "status": "success"
            },
            {
                "id": 2,
                "action": "password_change",
                "timestamp": str(datetime.now()),
                "status": "success"
            }
        ]
        
        # Set audit logs
        set_result = cache_service.set_audit_logs(user_id, test_logs)
        self.log_test("Audit Log Cache", "Set Audit Logs", set_result,
                     f"Set {len(test_logs)} audit logs for user_id: {user_id}")
        
        # Get audit logs
        cached_logs = cache_service.get_audit_logs(user_id)
        is_valid = cached_logs is not None and len(cached_logs) == len(test_logs)
        self.log_test("Audit Log Cache", "Get Audit Logs", is_valid,
                     f"Retrieved {len(cached_logs) if cached_logs else 0} audit logs")
    
    def test_audit_log_cache_invalidation(self):
        """Test audit log cache invalidation"""
        print("\n📋 AUDIT LOG CACHE: Invalidation")
        print("=" * 50)
        
        user_id = 99
        test_logs = [{"id": 99, "action": "test"}]
        
        cache_service.set_audit_logs(user_id, test_logs)
        
        # Invalidate
        cache_service.invalidate_audit_logs(user_id)
        
        # Verify it's gone
        cached_after = cache_service.get_audit_logs(user_id)
        self.log_test("Audit Log Cache", "Post-invalidation Check", cached_after is None,
                     f"Cached after invalidation: {cached_after is not None}")
    
    # ==================== COMPREHENSIVE CACHE TESTS ====================
    
    def test_comprehensive_cache_invalidation(self):
        """Test invalidating all user cache"""
        print("\n📋 COMPREHENSIVE: All User Cache Invalidation")
        print("=" * 50)
        
        user_id = 999
        
        # Set all types of cache
        cache_service.set_user_profile(user_id, {"id": user_id, "username": "test999"})
        cache_service.set_user_sessions(user_id, [{"session_id": "sess999"}])
        cache_service.set_user_permissions(user_id, [{"resource": "test", "action": "read"}])
        cache_service.set_audit_logs(user_id, [{"id": 999, "action": "test"}])
        
        self.log_test("Comprehensive Cache", "Pre-invalidation Setup", True,
                     f"Set all cache types for user_id: {user_id}")
        
        # Invalidate all
        invalidate_result = cache_service.invalidate_all_user_cache(user_id)
        self.log_test("Comprehensive Cache", "Invalidate All", invalidate_result,
                     f"Invalidated all cache types: {invalidate_result}")
        
        # Verify all cleared
        profile_after = cache_service.get_user_profile(user_id)
        sessions_after = cache_service.get_user_sessions(user_id)
        permissions_after = cache_service.get_user_permissions(user_id)
        logs_after = cache_service.get_audit_logs(user_id)
        
        all_cleared = (profile_after is None and 
                      sessions_after is None and 
                      permissions_after is None and 
                      logs_after is None)
        
        self.log_test("Comprehensive Cache", "Verify All Cleared", all_cleared,
                     f"Profile: {profile_after is None}, Sessions: {sessions_after is None}, " +
                     f"Permissions: {permissions_after is None}, Logs: {logs_after is None}")
    
    def test_cache_nonexistent_user(self):
        """Test cache operations with non-existent user"""
        print("\n📋 EDGE CASES: Non-existent User")
        print("=" * 50)
        
        user_id = 999999
        
        # Try to get non-existent cache
        profile = cache_service.get_user_profile(user_id)
        sessions = cache_service.get_user_sessions(user_id)
        permissions = cache_service.get_user_permissions(user_id)
        logs = cache_service.get_audit_logs(user_id)
        
        all_none = (profile is None and sessions is None and 
                   permissions is None and logs is None)
        
        self.log_test("Edge Cases", "Non-existent User Cache", all_none,
                     f"All cache types return None for non-existent user")
    
    # ==================== RUN ALL TESTS ====================
    
    def run_all_tests(self):
        """Run all cache service tests"""
        print("\n" + "=" * 60)
        print("🚀 CACHE SERVICE COMPREHENSIVE TEST SUITE")
        print("=" * 60)
        
        # Profile cache tests
        self.test_profile_cache_set_get()
        self.test_profile_cache_invalidation()
        self.test_profile_cache_multiple_users()
        
        # Session cache tests
        self.test_session_cache_set_get()
        self.test_session_cache_invalidation()
        
        # Permission cache tests
        self.test_permission_cache_set_get()
        self.test_permission_cache_invalidation()
        
        # Audit log cache tests
        self.test_audit_log_cache_set_get()
        self.test_audit_log_cache_invalidation()
        
        # Comprehensive tests
        self.test_comprehensive_cache_invalidation()
        self.test_cache_nonexistent_user()
        
        # Print summary
        self.print_summary()
    
    def print_summary(self):
        """Print test summary"""
        print("\n" + "=" * 60)
        print("📊 TEST SUMMARY")
        print("=" * 60)
        
        success_rate = (self.passed_tests / self.total_tests * 100) if self.total_tests > 0 else 0
        
        print(f"Total Tests: {self.total_tests}")
        print(f"Passed: {self.passed_tests}")
        print(f"Failed: {self.total_tests - self.passed_tests}")
        print(f"Success Rate: {success_rate:.1f}%")
        
        if success_rate == 100:
            print("\n✅ EXCELLENT: All cache service tests passed!")
        elif success_rate >= 80:
            print("\n✅ GOOD: Most cache service tests passed!")
        else:
            print("\n⚠️  WARNING: Some cache service tests failed")
        
        print("=" * 60)


if __name__ == "__main__":
    tester = CacheServiceTester()
    tester.run_all_tests()

