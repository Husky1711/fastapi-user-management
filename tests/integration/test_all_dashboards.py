"""
Comprehensive test for User and Admin Dashboard APIs
"""

import sys
import json
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import requests
from typing import Dict, Any

BASE_URL = "http://localhost:8000"


def print_test_header(test_name: str):
    """Print formatted test header"""
    print(f"\n{'='*60}")
    print(f"🔍 {test_name}")
    print('='*60)


def print_result(test_name: str, passed: bool, details: str = ""):
    """Print formatted test result"""
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"  {status} - {test_name}")
    if details:
        print(f"      {details}")


def test_all_dashboards():
    """Test both User and Admin dashboards"""
    
    results = []
    
    # ==========================================================================
    # USER DASHBOARD TESTS
    # ==========================================================================
    
    print_test_header("👤 USER DASHBOARD TESTS")
    
    # Login as regular user
    login_data = {
        "username": "test_dashboard_admin",  # This is admin but we'll test user endpoints too
        "password": "TestDashboardPass123!"
    }
    
    response = requests.post(
        f"{BASE_URL}/api/v1/login",
        json=login_data
    )
    
    if response.status_code != 200:
        print(f"❌ Login failed: {response.text}")
        return results
    
    data = response.json()
    access_token = data.get("access_token")
    
    if not access_token:
        print(f"❌ No access token received")
        return results
    
    print(f"✅ Login successful")
    headers = {"Authorization": f"Bearer {access_token}"}
    
    # 1. User Overview
    print(f"\n📊 Testing User Overview...")
    response = requests.get(
        f"{BASE_URL}/api/v1/dashboard/user/overview",
        headers=headers
    )
    
    passed = response.status_code == 200
    results.append(("User Overview Status", passed))
    print_result("User Overview Status", passed, f"Status: {response.status_code}")
    
    if passed:
        data = response.json()
        results.append(("User Overview Has Profile", "profile" in data))
        results.append(("User Overview Has Sessions", "active_sessions" in data))
        results.append(("User Overview Has Last Login", "last_login" in data))
        print(f"   Profile: {data.get('profile', {}).get('username', 'N/A')}")
        print(f"   Active Sessions: {data.get('active_sessions', 0)}")
    
    # 2. User Activity
    print(f"\n📈 Testing User Activity...")
    response = requests.get(
        f"{BASE_URL}/api/v1/dashboard/user/activity",
        headers=headers
    )
    
    passed = response.status_code == 200
    results.append(("User Activity Status", passed))
    print_result("User Activity Status", passed, f"Status: {response.status_code}")
    
    if passed:
        data = response.json()
        results.append(("User Activity Has Activity", "recent_activity" in data))
        results.append(("User Activity Has Stats", "total_logins_today" in data))
        activity_count = len(data.get('recent_activity', []))
        print(f"   Recent Activity Items: {activity_count}")
        print(f"   Logins Today: {data.get('total_logins_today', 0)}")
    
    # 3. User Sessions
    print(f"\n🔐 Testing User Sessions...")
    response = requests.get(
        f"{BASE_URL}/api/v1/dashboard/user/sessions",
        headers=headers
    )
    
    passed = response.status_code == 200
    results.append(("User Sessions Status", passed))
    print_result("User Sessions Status", passed, f"Status: {response.status_code}")
    
    if passed:
        data = response.json()
        results.append(("User Sessions Has Sessions", "active_sessions" in data))
        results.append(("User Sessions Has Total", "total_sessions" in data))
        sessions_count = len(data.get('active_sessions', []))
        print(f"   Active Sessions: {sessions_count}")
        print(f"   Total Sessions: {data.get('total_sessions', 0)}")
    
    # ==========================================================================
    # ADMIN DASHBOARD TESTS
    # ==========================================================================
    
    print_test_header("👨‍💼 ADMIN DASHBOARD TESTS")
    
    # Use the same admin token
    # 4. Admin Overview
    print(f"\n📊 Testing Admin Overview...")
    response = requests.get(
        f"{BASE_URL}/api/v1/dashboard/admin/overview",
        headers=headers
    )
    
    passed = response.status_code == 200
    results.append(("Admin Overview Status", passed))
    print_result("Admin Overview Status", passed, f"Status: {response.status_code}")
    
    if passed:
        data = response.json()
        results.append(("Admin Overview Has Users", "total_users" in data))
        results.append(("Admin Overview Has Stats", "today_stats" in data))
        print(f"   Total Users: {data.get('total_users', 0)}")
        print(f"   Active Sessions: {data.get('active_sessions', 0)}")
        print(f"   Today's Stats: {data.get('today_stats', {})}")
    
    # 5. Admin Users Stats
    print(f"\n👥 Testing Admin Users Stats...")
    response = requests.get(
        f"{BASE_URL}/api/v1/dashboard/admin/users/stats",
        headers=headers
    )
    
    passed = response.status_code == 200
    results.append(("Admin Users Stats Status", passed))
    print_result("Admin Users Stats Status", passed, f"Status: {response.status_code}")
    
    if passed:
        data = response.json()
        results.append(("Admin Users Stats Has Counts", "users_by_status" in data))
        results.append(("Admin Users Stats Has Recent", "recent_users" in data))
        print(f"   Total Users: {data.get('total_users', 0)}")
        print(f"   Active Users: {data.get('active_users', 0)}")
        recent_count = len(data.get('recent_users', []))
        print(f"   Recent Users: {recent_count}")
    
    # 6. Admin Activity Stats
    print(f"\n📈 Testing Admin Activity Stats...")
    response = requests.get(
        f"{BASE_URL}/api/v1/dashboard/admin/activity/stats",
        headers=headers
    )
    
    passed = response.status_code == 200
    results.append(("Admin Activity Stats Status", passed))
    print_result("Admin Activity Stats Status", passed, f"Status: {response.status_code}")
    
    if passed:
        data = response.json()
        results.append(("Admin Activity Has Total", "total_activity_today" in data))
        results.append(("Admin Activity Has By Type", "activity_by_type" in data))
        results.append(("Admin Activity Has Recent", "recent_activity" in data))
        print(f"   Total Activity Today: {data.get('total_activity_today', 0)}")
        activity_types = len(data.get('activity_by_type', {}))
        print(f"   Activity Types: {activity_types}")
        recent_count = len(data.get('recent_activity', []))
        print(f"   Recent Activity: {recent_count}")
    
    # Summary
    print_test_header("📊 COMPREHENSIVE TEST SUMMARY")
    
    total_tests = len(results)
    passed_tests = sum(1 for _, passed in results if passed)
    success_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0
    
    print(f"Total Tests: {total_tests}")
    print(f"Passed: {passed_tests}")
    print(f"Failed: {total_tests - passed_tests}")
    print(f"Success Rate: {success_rate:.1f}%")
    
    print(f"\n{'─'*60}")
    print(f"USER DASHBOARD:")
    user_tests = [r for r in results if 'User' in r[0]]
    user_passed = sum(1 for _, p in user_tests if p)
    print(f"  Tests: {len(user_tests)}")
    print(f"  Passed: {user_passed}")
    
    print(f"\n{'─'*60}")
    print(f"ADMIN DASHBOARD:")
    admin_tests = [r for r in results if 'Admin' in r[0]]
    admin_passed = sum(1 for _, p in admin_tests if p)
    print(f"  Tests: {len(admin_tests)}")
    print(f"  Passed: {admin_passed}")
    
    print(f"\n{'─'*60}")
    
    if success_rate == 100.0:
        print("\n✅ PERFECT: All dashboard tests passed!")
    elif success_rate >= 95.0:
        print("\n✅ EXCELLENT: Almost all dashboard tests passed!")
    elif success_rate >= 90.0:
        print("\n✅ GOOD: Most dashboard tests passed!")
    else:
        print("\n⚠️  Some tests failed. Review the output above.")
    
    print('='*60 + '\n')
    
    return results


if __name__ == "__main__":
    print('='*60)
    print("🚀 COMPREHENSIVE DASHBOARD API TESTS")
    print("👤 User Dashboard + 👨‍💼 Admin Dashboard")
    print('='*60)
    
    test_all_dashboards()
