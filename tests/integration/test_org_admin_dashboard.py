"""
Test Organization Admin Dashboard APIs
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


def test_org_admin_dashboard():
    """Test all organization admin dashboard endpoints"""
    
    results = []
    
    # Login as organization admin
    print_test_header("🔐 Logging in as Organization Admin...")
    
    login_data = {
        "username": "test_org_admin",
        "password": "TestOrgAdminPass123!"
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
    
    # 1. Organization Admin Overview
    print_test_header("📊 Org Admin Overview")
    
    response = requests.get(
        f"{BASE_URL}/api/v1/dashboard/organization-admin/overview",
        headers=headers
    )
    
    passed = response.status_code == 200
    results.append(("Org Admin Overview Status", passed))
    print_result("Org Admin Overview Status", passed, f"Status: {response.status_code}")
    
    if passed:
        data = response.json()
        required_fields = ["organization_id", "total_users", "active_users", "users_by_role", "today_stats"]
        
        for field in required_fields:
            has_field = field in data
            results.append((f"Response Has {field}", has_field))
            print_result(
                f"Response Has {field}",
                has_field,
                f"{field}: {data.get(field, 'N/A')}"
            )
        
        print(f"   Organization ID: {data.get('organization_id', 'N/A')}")
        print(f"   Total Users: {data.get('total_users', 0)}")
        print(f"   Active Users: {data.get('active_users', 0)}")
    
    # 2. Organization Admin Users Stats
    print_test_header("👥 Org Admin Users Stats")
    
    response = requests.get(
        f"{BASE_URL}/api/v1/dashboard/organization-admin/users/stats",
        headers=headers
    )
    
    passed = response.status_code == 200
    results.append(("Org Admin Users Stats Status", passed))
    print_result("Org Admin Users Stats Status", passed, f"Status: {response.status_code}")
    
    if passed:
        data = response.json()
        required_fields = ["total_users", "users_by_role", "users_by_status", "recent_users"]
        
        for field in required_fields:
            has_field = field in data
            results.append((f"Response Has {field}", has_field))
            
            if field == "recent_users":
                count = len(data.get(field, []))
                print_result(
                    f"Response Has {field}",
                    has_field,
                    f"Count: {count}"
                )
            else:
                print_result(
                    f"Response Has {field}",
                    has_field,
                    f"{field}: {data.get(field, 'N/A')}"
                )
        
        print(f"   Total Users: {data.get('total_users', 0)}")
        print(f"   By Role: {data.get('users_by_role', {})}")
        print(f"   By Status: {data.get('users_by_status', {})}")
    
    # 3. Organization Admin Sessions Stats
    print_test_header("🔐 Org Admin Sessions Stats")
    
    response = requests.get(
        f"{BASE_URL}/api/v1/dashboard/organization-admin/sessions/stats",
        headers=headers
    )
    
    passed = response.status_code == 200
    results.append(("Org Admin Sessions Stats Status", passed))
    print_result("Org Admin Sessions Stats Status", passed, f"Status: {response.status_code}")
    
    if passed:
        data = response.json()
        required_fields = ["total_sessions", "active_sessions", "revoked_sessions", "recent_sessions"]
        
        for field in required_fields:
            has_field = field in data
            results.append((f"Response Has {field}", has_field))
            
            if field == "recent_sessions":
                count = len(data.get(field, []))
                print_result(
                    f"Response Has {field}",
                    has_field,
                    f"Count: {count}"
                )
            else:
                print_result(
                    f"Response Has {field}",
                    has_field,
                    f"{field}: {data.get(field, 'N/A')}"
                )
        
        print(f"   Total Sessions: {data.get('total_sessions', 0)}")
        print(f"   Active Sessions: {data.get('active_sessions', 0)}")
        print(f"   Revoked Sessions: {data.get('revoked_sessions', 0)}")
    
    # Summary
    print_test_header("📊 TEST SUMMARY")
    
    total_tests = len(results)
    passed_tests = sum(1 for _, passed in results if passed)
    success_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0
    
    print(f"Total Tests: {total_tests}")
    print(f"Passed: {passed_tests}")
    print(f"Failed: {total_tests - passed_tests}")
    print(f"Success Rate: {success_rate:.1f}%")
    
    if success_rate == 100.0:
        print("\n✅ EXCELLENT: All organization admin dashboard tests passed!")
    elif success_rate >= 90.0:
        print("\n✅ GOOD: Most organization admin dashboard tests passed!")
    else:
        print("\n⚠️  Some tests failed. Review the output above.")
    
    print('='*60 + '\n')
    
    return results


if __name__ == "__main__":
    print('='*60)
    print("🏢 ORGANIZATION ADMIN DASHBOARD API TESTS")
    print('='*60)
    
    test_org_admin_dashboard()
