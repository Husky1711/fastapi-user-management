"""
Integration Tests for User Dashboard APIs
"""

import sys
from pathlib import Path
import requests
import time

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


class UserDashboardTester:
    """Test User Dashboard endpoints"""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.results = []
        self.total_tests = 0
        self.passed_tests = 0
    
    def log_test(self, test_name: str, passed: bool, details: str = ""):
        """Log test result"""
        self.total_tests += 1
        if passed:
            self.passed_tests += 1
        
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {status} - {test_name}")
        if details:
            print(f"      {details}")
    
    def test_overview_endpoint(self, token):
        """Test user dashboard overview endpoint"""
        print("\n📊 Testing User Dashboard Overview Endpoint")
        print("=" * 60)
        
        if not token:
            self.log_test("User Dashboard Overview", False, "No access token")
            return
        
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.get(f"{self.base_url}/api/v1/dashboard/user/overview", headers=headers)
        
        is_success = response.status_code == 200
        self.log_test("Overview Endpoint Status", is_success, f"Status: {response.status_code}")
        
        if is_success:
            data = response.json()
            has_profile = "profile" in data
            has_sessions = "active_sessions" in data
            has_last_login = "last_login" in data
            
            self.log_test("Response Has Profile", has_profile, f"Profile: {has_profile}")
            self.log_test("Response Has Sessions", has_sessions, f"Sessions: {has_sessions}")
            self.log_test("Response Has Last Login", has_last_login, f"Last Login: {has_last_login}")
            
            if has_profile:
                self.log_test("Profile Contains Username", "username" in data["profile"], 
                             f"Username: {data['profile'].get('username')}")
    
    def test_activity_endpoint(self, token):
        """Test user activity endpoint"""
        print("\n📊 Testing User Activity Endpoint")
        print("=" * 60)
        
        if not token:
            self.log_test("User Activity", False, "No access token")
            return
        
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.get(f"{self.base_url}/api/v1/dashboard/user/activity", headers=headers)
        
        is_success = response.status_code == 200
        self.log_test("Activity Endpoint Status", is_success, f"Status: {response.status_code}")
        
        if is_success:
            data = response.json()
            has_activity = "recent_activity" in data
            has_today = "total_logins_today" in data
            has_week = "total_logins_this_week" in data
            has_month = "total_logins_this_month" in data
            
            self.log_test("Response Has Recent Activity", has_activity, 
                         f"Activity items: {len(data.get('recent_activity', []))}")
            self.log_test("Response Has Today Stats", has_today, 
                         f"Today logins: {data.get('total_logins_today')}")
            self.log_test("Response Has Week Stats", has_week, 
                         f"Week logins: {data.get('total_logins_this_week')}")
            self.log_test("Response Has Month Stats", has_month, 
                         f"Month logins: {data.get('total_logins_this_month')}")
    
    def test_sessions_endpoint(self, token):
        """Test user sessions endpoint"""
        print("\n📊 Testing User Sessions Endpoint")
        print("=" * 60)
        
        if not token:
            self.log_test("User Sessions", False, "No access token")
            return
        
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.get(f"{self.base_url}/api/v1/dashboard/user/sessions", headers=headers)
        
        is_success = response.status_code == 200
        self.log_test("Sessions Endpoint Status", is_success, f"Status: {response.status_code}")
        
        if is_success:
            data = response.json()
            has_sessions = "active_sessions" in data
            has_total = "total_sessions" in data
            has_can_revoke = "can_revoke" in data
            
            self.log_test("Response Has Active Sessions", has_sessions, 
                         f"Active sessions: {len(data.get('active_sessions', []))}")
            self.log_test("Response Has Total Count", has_total, 
                         f"Total: {data.get('total_sessions')}")
            self.log_test("Response Has Can Revoke", has_can_revoke, 
                         f"Can revoke: {data.get('can_revoke')}")
    
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
            print("\n✅ EXCELLENT: All user dashboard tests passed!")
        elif success_rate >= 80:
            print("\n✅ GOOD: Most user dashboard tests passed!")
        else:
            print("\n⚠️  WARNING: Some user dashboard tests failed")
        
        print("=" * 60)
    
    def run_all_tests(self):
        """Run all user dashboard tests"""
        print("\n" + "=" * 60)
        print("🚀 USER DASHBOARD API TESTS")
        print("=" * 60)
        
        # Login to get token
        print("\n🔐 Logging in...")
        login_response = requests.post(
            f"{self.base_url}/api/v1/login",
            json={"username": "test_auth_user", "password": "NewSecurePass123"}
        )
        
        if login_response.status_code == 200:
            token = login_response.json().get("access_token")
            
            # Run tests
            self.test_overview_endpoint(token)
            self.test_activity_endpoint(token)
            self.test_sessions_endpoint(token)
            
            # Print summary
            self.print_summary()
        else:
            print("❌ Failed to login for testing")


if __name__ == "__main__":
    tester = UserDashboardTester()
    tester.run_all_tests()

