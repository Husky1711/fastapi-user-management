"""
Integration tests for Admin Dashboard APIs
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


def test_admin_dashboard():
    """Test all admin dashboard endpoints"""
    
    results = []
    
    # 1. Login as existing admin
    print_test_header("🔐 Logging in as Admin...")
    
    # Use the test admin we created
    login_data = {
        "username": "test_dashboard_admin",
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
    print(f"   Token: {access_token[:20]}...")
    
    headers = {"Authorization": f"Bearer {access_token}"}
    
    # 2. Test Admin Overview Endpoint
    print_test_header("📊 Admin Overview Endpoint")
    
    response = requests.get(
        f"{BASE_URL}/api/v1/dashboard/admin/overview",
        headers=headers
    )
    
    passed = response.status_code == 200
    results.append(("Admin Overview Endpoint Status", passed))
    print_result(
        "Admin Overview Endpoint Status",
        passed,
        f"Status: {response.status_code}"
    )
    
    if passed:
        data = response.json()
        
        # Check required fields
        required_fields = [
            "total_users",
            "active_users",
            "active_sessions",
            "today_stats"
        ]
        
        for field in required_fields:
            has_field = field in data
            results.append((f"Response Has {field}", has_field))
            print_result(
                f"Response Has {field}",
                has_field,
                f"{field}: {data.get(field, 'N/A')}"
            )
        
        print(f"   Full Response: {json.dumps(data, indent=2)}")
    else:
        # Show error details
        error_data = response.json()
        print(f"   Error: {json.dumps(error_data, indent=2)}")
    
    # 3. Test Admin Users Stats Endpoint
    print_test_header("👥 Admin Users Stats Endpoint")
    
    response = requests.get(
        f"{BASE_URL}/api/v1/dashboard/admin/users/stats",
        headers=headers
    )
    
    passed = response.status_code == 200
    results.append(("Admin Users Stats Endpoint Status", passed))
    print_result(
        "Admin Users Stats Endpoint Status",
        passed,
        f"Status: {response.status_code}"
    )
    
    if passed:
        data = response.json()
        
        # Check required fields
        required_fields = [
            "total_users",
            "active_users",
            "locked_users",
            "users_by_status",
            "recent_users"
        ]
        
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
        print(f"   Active Users: {data.get('active_users', 0)}")
        print(f"   Locked Users: {data.get('locked_users', 0)}")
    
    # 4. Test Admin Activity Stats Endpoint
    print_test_header("📈 Admin Activity Stats Endpoint")
    
    response = requests.get(
        f"{BASE_URL}/api/v1/dashboard/admin/activity/stats",
        headers=headers
    )
    
    passed = response.status_code == 200
    results.append(("Admin Activity Stats Endpoint Status", passed))
    print_result(
        "Admin Activity Stats Endpoint Status",
        passed,
        f"Status: {response.status_code}"
    )
    
    if passed:
        data = response.json()
        
        # Check required fields
        required_fields = [
            "total_activity_today",
            "activity_by_type",
            "recent_activity"
        ]
        
        for field in required_fields:
            has_field = field in data
            results.append((f"Response Has {field}", has_field))
            
            if field == "recent_activity":
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
        
        print(f"   Total Activity Today: {data.get('total_activity_today', 0)}")
        print(f"   Activity Types: {len(data.get('activity_by_type', {}))}")
    else:
        # Show error details
        error_data = response.json()
        print(f"   Error: {json.dumps(error_data, indent=2)}")
    
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
        print("\n✅ EXCELLENT: All admin dashboard tests passed!")
    elif success_rate >= 90.0:
        print("\n✅ GOOD: Most admin dashboard tests passed!")
    else:
        print("\n⚠️  Some tests failed. Review the output above.")
    
    print('='*60 + '\n')
    
    return results


if __name__ == "__main__":
    print('='*60)
    print("🚀 ADMIN DASHBOARD API TESTS")
    print('='*60)
    
    test_admin_dashboard()
