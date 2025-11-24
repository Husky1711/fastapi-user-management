"""
Test Organization-level Data Isolation
Verify that users/admins in different organizations can't access each other's data
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import requests
from utils.database import SessionLocal
from models.user_model import User
from utils.jwt_config import get_password_hash

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


def create_test_users():
    """Create test users in different organizations"""
    db = SessionLocal()
    
    # Org 1 Users
    users = [
        {
            "username": "org1_admin",
            "password": "TestPass123!",
            "role": "admin",
            "org_id": 2,  # Different from default org 1
            "status": "active"
        },
        {
            "username": "org1_user",
            "password": "TestPass123!",
            "role": "user",
            "org_id": 2,
            "status": "active"
        },
        {
            "username": "org2_admin",
            "password": "TestPass123!",
            "role": "admin",
            "org_id": 3,
            "status": "active"
        },
        {
            "username": "org2_user",
            "password": "TestPass123!",
            "role": "user",
            "org_id": 3,
            "status": "active"
        }
    ]
    
    created = []
    
    for user_data in users:
        # Check if user exists
        existing = db.query(User).filter(User.username == user_data["username"]).first()
        
        if not existing:
            # Create user
            password = user_data["password"]
            hashed_password = get_password_hash(password)
            
            new_user = User(
                username=user_data["username"],
                email=f"{user_data['username']}@test.com",
                password=hashed_password,
                role=user_data["role"],
                organization_id=user_data["org_id"],
                phone_number="1234567890",
                status=user_data["status"]
            )
            
            db.add(new_user)
            db.commit()
            db.refresh(new_user)
            created.append(new_user.username)
    
    db.close()
    
    if created:
        print(f"✅ Created test users: {', '.join(created)}")
    else:
        print(f"✅ Test users already exist")
    
    return users


def login_and_get_token(username: str, password: str):
    """Login and return access token"""
    response = requests.post(
        f"{BASE_URL}/api/v1/login",
        json={"username": username, "password": password}
    )
    
    if response.status_code == 200:
        return response.json().get("access_token")
    return None


def get_user_count_from_dashboard(access_token: str, dashboard_type: str):
    """Extract user count from dashboard response"""
    headers = {"Authorization": f"Bearer {access_token}"}
    
    endpoint_map = {
        "admin": "/api/v1/dashboard/admin/overview",
        "org_admin": "/api/v1/dashboard/organization-admin/overview",
        "user": "/api/v1/dashboard/user/overview"
    }
    
    endpoint = endpoint_map.get(dashboard_type)
    if not endpoint:
        return None
    
    response = requests.get(f"{BASE_URL}{endpoint}", headers=headers)
    
    if response.status_code == 200:
        data = response.json()
        
        # Try different fields based on dashboard type
        if dashboard_type == "admin":
            return data.get("total_users")
        elif dashboard_type == "org_admin":
            return data.get("total_users")
        elif dashboard_type == "user":
            return 1  # User dashboard doesn't show user count, return 1 (self)
    
    return None


def test_organization_isolation():
    """Test organization-level data isolation"""
    
    print("\n" + "="*70)
    print("🧪 ORGANIZATION-LEVEL DATA ISOLATION TEST")
    print("="*70)
    
    results = []
    
    # Create test users in different orgs
    print_header("SETUP: Creating Test Users")
    test_users = create_test_users()
    
    # =======================================================================
    # TEST 1: Admin in Org 2 should only see Org 2 users
    # =======================================================================
    
    print_header("TEST 1: Admin in Organization 2")
    
    # Login as org2_admin
    token = login_and_get_token("org2_admin", "TestPass123!")
    
    if token:
        # Get admin overview
        user_count = get_user_count_from_dashboard(token, "admin")
        
        # Count actual users in org 3
        db = SessionLocal()
        actual_count = db.query(User).filter(User.organization_id == 3).count()
        db.close()
        
        print(f"   Dashboard shows: {user_count} users")
        print(f"   Actual org 3 users: {actual_count} users")
        
        # Should only see org 3 users (not org 1 or org 2)
        passed = user_count == actual_count if user_count else False
        results.append(("Org 2 Admin sees only Org 2 users", passed))
        print_result(
            "Org 2 Admin sees only Org 2 users",
            passed,
            f"Expected {actual_count}, Got {user_count}"
        )
    else:
        print("   ❌ Could not login as org2_admin")
        results.append(("Org 2 Admin login", False))
    
    # =======================================================================
    # TEST 2: Admin in Org 3 should only see Org 3 users
    # =======================================================================
    
    print_header("TEST 2: Org Admin in Organization 3")
    
    # First, create an org admin in org 3
    db = SessionLocal()
    
    # Check if org3_admin exists
    existing = db.query(User).filter(User.username == "org3_admin").first()
    
    if not existing:
        password = "TestPass123!"
        hashed_password = get_password_hash(password)
        
        new_admin = User(
            username="org3_admin",
            email="org3_admin@test.com",
            password=hashed_password,
            role="organization_admin",
            organization_id=3,
            phone_number="1234567890",
            status="active"
        )
        
        db.add(new_admin)
        db.commit()
        print("   ✅ Created org3_admin")
    
    db.close()
    
    # Login as org3_admin
    token = login_and_get_token("org3_admin", "TestPass123!")
    
    if token:
        # Get org admin overview
        user_count = get_user_count_from_dashboard(token, "org_admin")
        
        # Count actual users in org 3
        db = SessionLocal()
        actual_count = db.query(User).filter(User.organization_id == 3).count()
        db.close()
        
        print(f"   Dashboard shows: {user_count} users")
        print(f"   Actual org 3 users: {actual_count} users")
        
        passed = user_count == actual_count if user_count else False
        results.append(("Org 3 Admin sees only Org 3 users", passed))
        print_result(
            "Org 3 Admin sees only Org 3 users",
            passed,
            f"Expected {actual_count}, Got {user_count}"
        )
    else:
        print("   ❌ Could not login as org3_admin")
        results.append(("Org 3 Admin login", False))
    
    # =======================================================================
    # TEST 3: Users can't see other organization's data via admin dashboard
    # =======================================================================
    
    print_header("TEST 3: Cross-Organization Access Control")
    
    # Login as org1_user (regular user in org 2)
    token = login_and_get_token("org1_user", "TestPass123!")
    
    if token:
        # Try to access admin dashboard (should fail or only show org 2 data)
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.get(
            f"{BASE_URL}/api/v1/dashboard/admin/overview",
            headers=headers
        )
        
        # Regular user should get 403
        passed = response.status_code == 403
        results.append(("Regular user cannot access admin dashboard", passed))
        print_result(
            "Regular user cannot access admin dashboard",
            passed,
            f"Status: {response.status_code}"
        )
    
    # =======================================================================
    # TEST 4: Admins can't access organization admin endpoints
    # =======================================================================
    
    print_header("TEST 4: Role-Based Access Control")
    
    # Login as org2_admin (admin, not org admin)
    token = login_and_get_token("org2_admin", "TestPass123!")
    
    if token:
        # Try to access organization admin dashboard
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.get(
            f"{BASE_URL}/api/v1/dashboard/organization-admin/overview",
            headers=headers
        )
        
        # Regular admin should get 403
        passed = response.status_code == 403
        results.append(("Admin cannot access org admin endpoints", passed))
        print_result(
            "Admin cannot access org admin endpoints",
            passed,
            f"Status: {response.status_code}"
        )
    
    # =======================================================================
    # SUMMARY
    # =======================================================================
    
    print_header("ISOLATION TEST SUMMARY")
    
    total_tests = len(results)
    passed_tests = sum(1 for _, passed in results if passed)
    success_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0
    
    print(f"\nTotal Tests: {total_tests}")
    print(f"Passed: {passed_tests}")
    print(f"Failed: {total_tests - passed_tests}")
    print(f"Success Rate: {success_rate:.1f}%")
    
    if success_rate == 100.0:
        print("\n✅ PERFECT: Data isolation working correctly!")
        print("   ✅ Users in different orgs can't see each other's data")
        print("   ✅ Role-based access control working")
        print("   ✅ Organization-level boundaries enforced")
    elif success_rate >= 90.0:
        print("\n✅ GOOD: Most isolation tests passed!")
    else:
        print("\n⚠️  Isolation issues detected!")
    
    print('='*70 + '\n')
    
    return results


if __name__ == "__main__":
    test_organization_isolation()
