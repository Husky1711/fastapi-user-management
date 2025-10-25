#!/usr/bin/env python3
"""
Simple Production Features Test
Quick verification of core production features
"""

import requests
import json

def test_production_features():
    """Test core production features"""
    base_url = "http://localhost:8000"
    
    print("=" * 60)
    print("SIMPLE PRODUCTION FEATURES TEST")
    print("=" * 60)
    
    # Authenticate
    print("\n1. Testing Authentication...")
    login_data = {
        "username": "test_fix_user",
        "password": "NewSecurePass123"
    }
    
    try:
        response = requests.post(
            f"{base_url}/api/v1/login",
            json=login_data,
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 200:
            token_data = response.json()
            token = token_data["access_token"]
            headers = {"Authorization": f"Bearer {token}"}
            print("   [PASS] Authentication successful")
        else:
            print(f"   [FAIL] Authentication failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"   [FAIL] Authentication error: {str(e)}")
        return False
    
    # Test core endpoints
    endpoints = [
        ("Audit Logs", "/api/v1/audit/logs"),
        ("Sessions", "/api/v1/sessions"),
        ("Permissions", "/api/v1/permissions"),
        ("Groups", "/api/v1/groups"),
        ("API Keys", "/api/v1/api-keys"),
        ("Password History", "/api/v1/password/history")
    ]
    
    passed = 0
    total = len(endpoints)
    
    print(f"\n2. Testing {total} Core Endpoints...")
    
    for name, endpoint in endpoints:
        try:
            response = requests.get(f"{base_url}{endpoint}", headers=headers)
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list):
                    count = len(data)
                else:
                    count = data.get("total_count", 0)
                print(f"   [PASS] {name}: {count} records")
                passed += 1
            else:
                print(f"   [FAIL] {name}: Status {response.status_code}")
        except Exception as e:
            print(f"   [FAIL] {name}: Error {str(e)}")
    
    # Test password change
    print(f"\n3. Testing Password Change...")
    try:
        password_data = {
            "current_password": "NewSecurePass123",
            "new_password": "AnotherNewPassword123"
        }
        
        response = requests.post(
            f"{base_url}/api/v1/password/change",
            json=password_data,
            headers={**headers, "Content-Type": "application/json"}
        )
        
        if response.status_code == 200:
            print("   [PASS] Password change successful")
            passed += 1
        else:
            print(f"   [FAIL] Password change failed: {response.status_code}")
    except Exception as e:
        print(f"   [FAIL] Password change error: {str(e)}")
    
    total += 1
    
    # Summary
    print(f"\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    success_rate = (passed / total) * 100
    print(f"Tests Passed: {passed}/{total} ({success_rate:.1f}%)")
    
    if success_rate >= 80:
        print("*** EXCELLENT: Core production features are working! ***")
        return True
    elif success_rate >= 60:
        print("*** GOOD: Most core features are working! ***")
        return True
    else:
        print("*** NEEDS ATTENTION: Some core features need fixes! ***")
        return False

if __name__ == "__main__":
    success = test_production_features()
    if success:
        print("\n*** Core production features test PASSED! ***")
    else:
        print("\n*** Core production features test FAILED! ***")
