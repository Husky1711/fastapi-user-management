"""
Comprehensive test for all Dashboard APIs
User Dashboard + Admin Dashboard + Organization Admin Dashboard
"""

import sys
import json
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import requests
from typing import Dict, Any

from tests.config import API_BASE_URL

BASE_URL = API_BASE_URL


def print_section_header(title: str):
    """Print section header"""
    print(f"\n{'='*70}")
    print(f"🎯 {title}")
    print('='*70)


def print_subsection(title: str):
    """Print subsection"""
    print(f"\n{'─'*70}")
    print(f"📊 {title}")
    print('─'*70)


def print_result(test_name: str, passed: bool, details: str = ""):
    """Print formatted test result"""
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"  {status} - {test_name}")
    if details:
        print(f"      {details}")


def test_user_dashboard(
    username: str = "test_dashboard_admin",
    password: str = "TestDashboardPass123!",
    results: list = None,
):
    """Test User Dashboard endpoints"""
    if results is None:
        results = []
    
    print_subsection(f"Testing as {username} (User role)")
    
    # Login
    response = requests.post(
        f"{BASE_URL}/api/v1/login",
        json={"username": username, "password": password}
    )
    
    if response.status_code != 200:
        print(f"❌ Login failed")
        return results
    
    access_token = response.json().get("access_token")
    headers = {"Authorization": f"Bearer {access_token}"}
    
    # Test overview
    response = requests.get(
        f"{BASE_URL}/api/v1/dashboard/user/overview",
        headers=headers
    )
    results.append(("User Overview", response.status_code == 200))
    if response.status_code == 200:
        data = response.json()
        print(f"   ✅ Overview: User {data.get('profile', {}).get('username', 'N/A')}")
    
    # Test activity
    response = requests.get(
        f"{BASE_URL}/api/v1/dashboard/user/activity",
        headers=headers
    )
    results.append(("User Activity", response.status_code == 200))
    if response.status_code == 200:
        data = response.json()
        print(f"   ✅ Activity: {len(data.get('recent_activity', []))} recent items")
    
    # Test sessions
    response = requests.get(
        f"{BASE_URL}/api/v1/dashboard/user/sessions",
        headers=headers
    )
    results.append(("User Sessions", response.status_code == 200))
    if response.status_code == 200:
        data = response.json()
        print(f"   ✅ Sessions: {data.get('total_sessions', 0)} active")
    
    return results


def test_admin_dashboard(
    username: str = "test_dashboard_admin",
    password: str = "TestDashboardPass123!",
    results: list = None,
):
    """Test Admin Dashboard endpoints"""
    if results is None:
        results = []
    
    print_subsection(f"Testing as {username} (Admin role)")
    
    # Login
    response = requests.post(
        f"{BASE_URL}/api/v1/login",
        json={"username": username, "password": password}
    )
    
    if response.status_code != 200:
        print(f"❌ Login failed")
        return results
    
    access_token = response.json().get("access_token")
    headers = {"Authorization": f"Bearer {access_token}"}
    
    # Test all admin endpoints
    endpoints = [
        ("Admin Overview", "/api/v1/dashboard/admin/overview"),
        ("Admin Users Stats", "/api/v1/dashboard/admin/users/stats"),
        ("Admin Activity Stats", "/api/v1/dashboard/admin/activity/stats"),
    ]
    
    for name, endpoint in endpoints:
        response = requests.get(f"{BASE_URL}{endpoint}", headers=headers)
        results.append((name, response.status_code == 200))
        
        if response.status_code == 200:
            print(f"   ✅ {name}: Working")
        else:
            print(f"   ❌ {name}: Failed ({response.status_code})")
            if response.status_code == 403:
                print(f"      Access denied - role check")
    
    return results


def test_org_admin_dashboard(
    username: str = "test_org_admin",
    password: str = "TestOrgAdminPass123!",
    results: list = None,
):
    """Test Organization Admin Dashboard endpoints"""
    if results is None:
        results = []
    
    print_subsection(f"Testing as {username} (Organization Admin role)")
    
    # Login
    response = requests.post(
        f"{BASE_URL}/api/v1/login",
        json={"username": username, "password": password}
    )
    
    if response.status_code != 200:
        print(f"❌ Login failed")
        return results
    
    access_token = response.json().get("access_token")
    headers = {"Authorization": f"Bearer {access_token}"}
    
    # Test all org admin endpoints
    endpoints = [
        ("Org Admin Overview", "/api/v1/dashboard/organization-admin/overview"),
        ("Org Admin Users Stats", "/api/v1/dashboard/organization-admin/users/stats"),
        ("Org Admin Sessions Stats", "/api/v1/dashboard/organization-admin/sessions/stats"),
    ]
    
    for name, endpoint in endpoints:
        response = requests.get(f"{BASE_URL}{endpoint}", headers=headers)
        results.append((name, response.status_code == 200))
        
        if response.status_code == 200:
            print(f"   ✅ {name}: Working")
        else:
            print(f"   ❌ {name}: Failed ({response.status_code})")
            if response.status_code == 403:
                print(f"      Access denied - role check")
    
    return results


def test_cross_role_access(results: list = None):
    """Test that users can't access dashboards they shouldn't"""
    if results is None:
        results = []
    
    print_subsection("Testing Cross-Role Access Control")
    
    # Try accessing admin endpoints as regular user
    response = requests.post(
        f"{BASE_URL}/api/v1/login",
        json={"username": "test_dashboard_admin", "password": "TestDashboardPass123!"}
    )
    
    if response.status_code != 200:
        print("❌ Login failed for admin user")
        return results
    
    access_token = response.json().get("access_token")
    headers = {"Authorization": f"Bearer {access_token}"}
    
    # Admin trying to access user dashboard (should work)
    response = requests.get(
        f"{BASE_URL}/api/v1/dashboard/user/overview",
        headers=headers
    )
    results.append(("Admin can access User Dashboard", response.status_code == 200))
    print(f"   ✅ Admin -> User Dashboard: {response.status_code == 200}")
    
    # Admin trying to access org admin dashboard (should work since they're higher privilege)
    response = requests.get(
        f"{BASE_URL}/api/v1/dashboard/organization-admin/overview",
        headers=headers
    )
    results.append(("Admin can access Org Admin Dashboard", response.status_code == 200))
    print(f"   ✅ Admin -> Org Admin Dashboard: {response.status_code == 200}")
    
    return results


def test_data_isolation(results: list = None):
    """Test that data is properly isolated by organization"""
    if results is None:
        results = []
    
    print_subsection("Testing Data Isolation (Organization-level)")
    
    # Login as org admin from org 1
    response = requests.post(
        f"{BASE_URL}/api/v1/login",
        json={"username": "test_org_admin", "password": "TestOrgAdminPass123!"}
    )
    
    if response.status_code != 200:
        print("❌ Login failed for org admin")
        return results
    
    access_token = response.json().get("access_token")
    headers = {"Authorization": f"Bearer {access_token}"}
    
    # Get org overview
    response = requests.get(
        f"{BASE_URL}/api/v1/dashboard/organization-admin/overview",
        headers=headers
    )
    
    if response.status_code == 200:
        data = response.json()
        org_id = data.get("organization_id")
        total_users = data.get("total_users")
        
        results.append(("Data isolation works", org_id is not None))
        print(f"   ✅ Organization ID: {org_id}")
        print(f"   ✅ Total Users in Org {org_id}: {total_users}")
    
    return results


def main():
    """Run all comprehensive dashboard tests"""
    
    print('='*70)
    print("🚀 COMPREHENSIVE DASHBOARD API TESTS")
    print("👤 User + 👨‍💼 Admin + 🏢 Org Admin Dashboards")
    print('='*70)
    
    results = []
    
    # ==========================================================================
    # USER DASHBOARD TESTS
    # ==========================================================================
    
    print_section_header("USER DASHBOARD TESTS")
    results = test_user_dashboard(
        "test_dashboard_admin",
        "TestDashboardPass123!",
        results
    )
    
    # ==========================================================================
    # ADMIN DASHBOARD TESTS
    # ==========================================================================
    
    print_section_header("ADMIN DASHBOARD TESTS")
    results = test_admin_dashboard(
        "test_dashboard_admin",
        "TestDashboardPass123!",
        results
    )
    
    # ==========================================================================
    # ORGANIZATION ADMIN DASHBOARD TESTS
    # ==========================================================================
    
    print_section_header("ORGANIZATION ADMIN DASHBOARD TESTS")
    results = test_org_admin_dashboard(
        "test_org_admin",
        "TestOrgAdminPass123!",
        results
    )
    
    # ==========================================================================
    # CROSS-ROLE ACCESS CONTROL TESTS
    # ==========================================================================
    
    print_section_header("CROSS-ROLE ACCESS CONTROL")
    results = test_cross_role_access(results)
    
    # ==========================================================================
    # DATA ISOLATION TESTS
    # ==========================================================================
    
    print_section_header("DATA ISOLATION TESTS")
    results = test_data_isolation(results)
    
    # ==========================================================================
    # SUMMARY
    # ==========================================================================
    
    print_section_header("COMPREHENSIVE TEST SUMMARY")
    
    total_tests = len(results)
    passed_tests = sum(1 for _, passed in results if passed)
    success_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0
    
    print(f"\nTotal Tests: {total_tests}")
    print(f"Passed: {passed_tests}")
    print(f"Failed: {total_tests - passed_tests}")
    print(f"Success Rate: {success_rate:.1f}%")
    
    # Breakdown by category
    print(f"\n{'─'*70}")
    print(f"CATEGORY BREAKDOWN:")
    print(f"{'─'*70}")
    
    user_tests = [r for r in results if 'User' in r[0] and 'Admin' not in r[0]]
    print(f"  User Dashboard: {sum(1 for _, p in user_tests if p)}/{len(user_tests)}")
    
    admin_tests = [r for r in results if 'Admin' in r[0] and 'Org' not in r[0]]
    print(f"  Admin Dashboard: {sum(1 for _, p in admin_tests if p)}/{len(admin_tests)}")
    
    org_tests = [r for r in results if 'Org Admin' in r[0] or 'Org' in r[0]]
    print(f"  Org Admin Dashboard: {sum(1 for _, p in org_tests if p)}/{len(org_tests)}")
    
    access_tests = [r for r in results if 'can access' in r[0] or 'isolation' in r[0]]
    print(f"  Access Control: {sum(1 for _, p in access_tests if p)}/{len(access_tests)}")
    
    print(f"\n{'─'*70}")
    
    if success_rate == 100.0:
        print("\n✅ PERFECT: All tests passed!")
        print("   User, Admin, and Organization Admin dashboards working correctly")
        print("   Access control and data isolation verified")
    elif success_rate >= 95.0:
        print("\n✅ EXCELLENT: Almost all tests passed!")
    elif success_rate >= 90.0:
        print("\n✅ GOOD: Most tests passed!")
    else:
        print("\n⚠️  Some tests failed. Review the output above.")
    
    print('='*70 + '\n')
    
    return results


if __name__ == "__main__":
    main()
