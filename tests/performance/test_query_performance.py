"""
Database Query Performance Tests
Tests query performance before and after database optimization
"""

import sys
import os
import time
from pathlib import Path
import requests

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from services.users import UserService
from utils.database import get_db


class QueryPerformanceTester:
    """Test database query performance"""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.results = []
    
    def measure_time(self, func, *args, **kwargs):
        """Measure execution time of a function"""
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        elapsed = (end_time - start_time) * 1000  # Convert to milliseconds
        return elapsed, result
    
    def test_profile_query_database(self, user_id):
        """Test direct database query for user profile"""
        print(f"\n📊 Testing Profile Query (Database) for user_id: {user_id}")
        
        db = next(get_db())
        
        # Measure query time
        elapsed, user = self.measure_time(
            UserService.get_user_by_id, db, user_id
        )
        
        db.close()
        
        status = "✅ PASS" if elapsed < 50 else "❌ FAIL"
        print(f"  {status} - Query time: {elapsed:.2f}ms (Target: < 50ms)")
        
        self.results.append({
            "test": "Profile Query (Database)",
            "time": elapsed,
            "target": 50,
            "status": "PASS" if elapsed < 50 else "FAIL"
        })
        
        return elapsed
    
    def test_profile_query_api(self, token, user_id):
        """Test API endpoint for user profile"""
        print(f"\n📊 Testing Profile Query (API) for user_id: {user_id}")
        
        headers = {"Authorization": f"Bearer {token}"}
        
        # First request (no cache)
        elapsed1, response1 = self.measure_time(
            requests.get, f"{self.base_url}/api/v1/users/{user_id}", headers=headers
        )
        
        # Second request (with cache)
        elapsed2, response2 = self.measure_time(
            requests.get, f"{self.base_url}/api/v1/users/{user_id}", headers=headers
        )
        
        status1 = "✅ PASS" if elapsed1 < 500 else "❌ FAIL"
        status2 = "✅ PASS" if elapsed2 < 100 else "❌ FAIL"
        
        print(f"  {status1} - First request (no cache): {elapsed1:.2f}ms (Target: < 500ms)")
        print(f"  {status2} - Second request (cached): {elapsed2:.2f}ms (Target: < 100ms)")
        
        cache_improvement = ((elapsed1 - elapsed2) / elapsed1) * 100
        print(f"  📈 Cache improvement: {cache_improvement:.1f}%")
        
        self.results.append({
            "test": "Profile Query (API - No Cache)",
            "time": elapsed1,
            "target": 500,
            "status": "PASS" if elapsed1 < 500 else "FAIL"
        })
        
        self.results.append({
            "test": "Profile Query (API - Cached)",
            "time": elapsed2,
            "target": 100,
            "status": "PASS" if elapsed2 < 100 else "FAIL"
        })
        
        return elapsed1, elapsed2
    
    def test_user_list_query(self, token):
        """Test user list query"""
        print(f"\n📊 Testing User List Query")
        
        headers = {"Authorization": f"Bearer {token}"}
        
        elapsed, _ = self.measure_time(
            requests.get, f"{self.base_url}/api/v1/users", headers=headers
        )
        
        status = "✅ PASS" if elapsed < 3000 else "❌ FAIL"
        print(f"  {status} - Query time: {elapsed:.2f}ms (Target: < 3000ms)")
        
        self.results.append({
            "test": "User List Query",
            "time": elapsed,
            "target": 3000,
            "status": "PASS" if elapsed < 3000 else "FAIL"
        })
        
        return elapsed
    
    def test_session_query(self, token):
        """Test session query"""
        print(f"\n📊 Testing Session Query")
        
        headers = {"Authorization": f"Bearer {token}"}
        
        elapsed, _ = self.measure_time(
            requests.get, f"{self.base_url}/api/v1/sessions", headers=headers
        )
        
        status = "✅ PASS" if elapsed < 3000 else "❌ FAIL"
        print(f"  {status} - Query time: {elapsed:.2f}ms (Target: < 3000ms)")
        
        self.results.append({
            "test": "Session Query",
            "time": elapsed,
            "target": 3000,
            "status": "PASS" if elapsed < 3000 else "FAIL"
        })
        
        return elapsed
    
    def test_audit_log_query(self, token):
        """Test audit log query"""
        print(f"\n📊 Testing Audit Log Query")
        
        headers = {"Authorization": f"Bearer {token}"}
        
        elapsed, _ = self.measure_time(
            requests.get, f"{self.base_url}/api/v1/audit/logs?limit=50", headers=headers
        )
        
        status = "✅ PASS" if elapsed < 3000 else "❌ FAIL"
        print(f"  {status} - Query time: {elapsed:.2f}ms (Target: < 3000ms)")
        
        self.results.append({
            "test": "Audit Log Query",
            "time": elapsed,
            "target": 3000,
            "status": "PASS" if elapsed < 3000 else "FAIL"
        })
        
        return elapsed
    
    def print_summary(self):
        """Print test summary"""
        print("\n" + "=" * 60)
        print("📊 PERFORMANCE TEST SUMMARY")
        print("=" * 60)
        
        total_tests = len(self.results)
        passed_tests = sum(1 for r in self.results if r["status"] == "PASS")
        failed_tests = total_tests - passed_tests
        
        print(f"Total Tests: {total_tests}")
        print(f"Passed: {passed_tests}")
        print(f"Failed: {failed_tests}")
        print(f"Success Rate: {(passed_tests/total_tests)*100:.1f}%")
        
        print("\nDetailed Results:")
        for result in self.results:
            status_icon = "✅" if result["status"] == "PASS" else "❌"
            print(f"  {status_icon} {result['test']}: {result['time']:.2f}ms (Target: < {result['target']}ms)")
        
        print("=" * 60)
    
    def run_all_tests(self):
        """Run all performance tests"""
        print("\n" + "=" * 60)
        print("⚡ DATABASE QUERY PERFORMANCE TESTS")
        print("=" * 60)
        
        # Login to get token
        print("\n🔐 Logging in to get access token...")
        login_response = requests.post(
            f"{self.base_url}/api/v1/login",
            json={"username": "test_auth_user", "password": "NewSecurePass123"}
        )
        
        if login_response.status_code == 200:
            token = login_response.json().get("access_token")
            user_id = 39  # test_auth_user ID
            
            # Run performance tests
            self.test_profile_query_database(user_id)
            self.test_profile_query_api(token, user_id)
            self.test_user_list_query(token)
            self.test_session_query(token)
            self.test_audit_log_query(token)
            
            # Print summary
            self.print_summary()
        else:
            print("❌ Failed to login for performance tests")


if __name__ == "__main__":
    tester = QueryPerformanceTester()
    tester.run_all_tests()

