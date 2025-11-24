"""
Test Super Admin Dashboard APIs
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


def print_header(title: str):
    """Print formatted header"""
    print(f"\n{'='*70}")
    print(f"🎯 {title}")
    print('='*70)


def print_result(test_name: str, passed: bool, details: str = ""):
    """Print formatted test result"""
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"  {status} - {test_name}")
    if details:
        print(f"      {details}")


def test_super_admin_dashboard():
    """Test all super admin dashboard endpoints"""
    
    print("\n" + "="*70)
    print("👑 SUPER ADMIN DASHBOARD API TESTS")
    print("="*70)
    
    results = []
    
    # Login as super admin
    print_header("Logging in as Super Admin")
    
    # Login with test_super_admin
    login_data = {"username": "test_super_admin", "password": "TestSuperAdminPass123!"}
    
    response = requests.post(
        f"{BASE_URL}/api/v1/login",
        json=login_data
    )
    
    if response.status_code != 200:
        print(f"❌ Login failed")
        print(f"   Response: {response.text}")
        return results
    
    data = response.json()
    access_token = data.get("access_token")
    
    if not access_token:
        print(f"❌ No access token received")
        return results
    
    print(f"✅ Login successful")
    headers = {"Authorization": f"Bearer {access_token}"}
    
    # Test endpoints
    endpoints = [
        ("Super Admin Overview", "/api/v1/dashboard/super-admin/overview"),
        ("Super Admin Users Stats", "/api/v1/dashboard/super-admin/users/stats"),
        ("Super Admin Organizations Stats", "/api/v1/dashboard/super-admin/organizations/stats"),
        ("Super Admin Sessions Stats", "/api/v1/dashboard/super-admin/sessions/stats"),
    ]
    
    for name, endpoint in endpoints:
        print_header(f"Testing {name}")
        
        response = requests.get(f"{BASE_URL}{endpoint}", headers=headers)
        passed = response.status_code == 200
        results.append((name, passed))
        
        print_result(name, passed, f"Status: {response.status_code}")
        
        if passed:
            data = response.json()
            
            # Show key metrics
            if "overview" in endpoint:
                print(f"   Organizations: {data.get('total_organizations', 0)}")
                print(f"   Users: {data.get('total_users', 0)}")
                print(f"   Active Sessions: {data.get('active_sessions', 0)}")
                print(f"   Today's Logins: {data.get('today_stats', {}).get('logins', 0)}")
            elif "users/stats" in endpoint:
                print(f"   Total Users: {data.get('total_users', 0)}")
                print(f"   Active Users: {data.get('active_users', 0)}")
                print(f"   Users Today: {data.get('users_today', 0)}")
                print(f"   Users This Month: {data.get('users_this_month', 0)}")
            elif "organizations/stats" in endpoint:
                print(f"   Total Orgs: {data.get('total_organizations', 0)}")
                print(f"   Active Orgs: {data.get('active_organizations', 0)}")
                print(f"   Orgs by Size: {data.get('organizations_by_size', {})}")
            elif "sessions/stats" in endpoint:
                print(f"   Total Sessions: {data.get('total_sessions', 0)}")
                print(f"   Active Sessions: {data.get('active_sessions', 0)}")
                print(f"   Revoked Sessions: {data.get('revoked_sessions', 0)}")
        else:
            error_data = response.json() if response.text else {}
            print(f"   Error: {error_data.get('detail', 'Unknown error')}")
    
    # Summary
    print_header("TEST SUMMARY")
    
    total_tests = len(results)
    passed_tests = sum(1 for _, passed in results if passed)
    success_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0
    
    print(f"\nTotal Tests: {total_tests}")
    print(f"Passed: {passed_tests}")
    print(f"Failed: {total_tests - passed_tests}")
    print(f"Success Rate: {success_rate:.1f}%")
    
    if success_rate == 100.0:
        print("\n✅ PERFECT: All super admin dashboard tests passed!")
    elif success_rate >= 90.0:
        print("\n✅ GOOD: Most super admin dashboard tests passed!")
    else:
        print("\n⚠️  Some tests failed. Review the output above.")
    
    print('='*70 + '\n')
    
    return results


if __name__ == "__main__":
    test_super_admin_dashboard()
