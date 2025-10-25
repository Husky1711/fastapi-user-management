#!/usr/bin/env python3
"""
Final Comprehensive Test - Auth + Users Migration
"""

import requests
import json

def final_comprehensive_test():
    base_url = 'http://localhost:8000'
    session = requests.Session()
    
    print('🎯 FINAL COMPREHENSIVE TEST - AUTH + USERS MIGRATION')
    print('=' * 60)
    
    results = {}
    total_tests = 0
    passed_tests = 0
    
    # 1. Basic Authentication
    print('\n1. BASIC AUTHENTICATION')
    print('-' * 30)
    
    login_data = {'username': 'test_auth_user', 'password': 'AnotherNewPass123'}
    response = session.post(f'{base_url}/api/v1/login', json=login_data)
    total_tests += 1
    if response.status_code == 200:
        passed_tests += 1
        results['basic_login'] = 'PASS'
        print('✅ Basic Login: PASS')
        
        data = response.json()
        token = data.get('access_token')
        refresh_token = data.get('refresh_token')
        
        # Test logout FIRST (before refresh)
        logout_data = {'refresh_token': refresh_token}
        response = session.post(f'{base_url}/api/v1/logout', json=logout_data)
        total_tests += 1
        if response.status_code == 200:
            passed_tests += 1
            results['logout'] = 'PASS'
            print('✅ Logout: PASS')
        else:
            results['logout'] = 'FAIL'
            print(f'❌ Logout: FAIL - {response.status_code}')
        
        # Re-login for refresh token test
        response = session.post(f'{base_url}/api/v1/login', json=login_data)
        if response.status_code == 200:
            data = response.json()
            refresh_token = data.get('refresh_token')
        
        # Test refresh token
        refresh_data = {'refresh_token': refresh_token}
        response = session.post(f'{base_url}/api/v1/refresh', json=refresh_data)
        total_tests += 1
        if response.status_code == 200:
            passed_tests += 1
            results['refresh_token'] = 'PASS'
            print('✅ Refresh Token: PASS')
        else:
            results['refresh_token'] = 'FAIL'
            print(f'❌ Refresh Token: FAIL - {response.status_code}')
    else:
        results['basic_login'] = 'FAIL'
        print(f'❌ Basic Login: FAIL - {response.status_code}')
    
    # 2. Enhanced Login Strategies
    print('\n2. ENHANCED LOGIN STRATEGIES')
    print('-' * 30)
    
    strategies = ['allow_multiple', 'replace_all', 'replace_same_device', 'limit_sessions']
    for strategy in strategies:
        response = session.post(f'{base_url}/api/v1/login-with-session-control?session_strategy={strategy}', json=login_data)
        total_tests += 1
        if response.status_code == 200:
            passed_tests += 1
            results[f'enhanced_login_{strategy}'] = 'PASS'
            print(f'✅ Enhanced Login ({strategy}): PASS')
        else:
            results[f'enhanced_login_{strategy}'] = 'FAIL'
            print(f'❌ Enhanced Login ({strategy}): FAIL - {response.status_code}')
    
    # 3. User Management APIs
    print('\n3. USER MANAGEMENT APIs')
    print('-' * 30)
    
    # Re-login for authenticated tests
    response = session.post(f'{base_url}/api/v1/login', json=login_data)
    if response.status_code == 200:
        data = response.json()
        token = data.get('access_token')
        headers = {'Authorization': f'Bearer {token}'}
        
        # Test profile endpoints
        endpoints = [
            ('/api/v1/profile', 'GET'),
            ('/api/v1/users', 'GET'),
            ('/api/v1/sessions', 'GET'),
            ('/api/v1/password/history', 'GET')
        ]
        
        for endpoint, method in endpoints:
            if method == 'GET':
                response = session.get(f'{base_url}{endpoint}', headers=headers)
            total_tests += 1
            if response.status_code == 200:
                passed_tests += 1
                results[f'endpoint_{endpoint.replace("/", "_")}'] = 'PASS'
                print(f'✅ {endpoint}: PASS')
            else:
                results[f'endpoint_{endpoint.replace("/", "_")}'] = 'FAIL'
                print(f'❌ {endpoint}: FAIL - {response.status_code}')
        
        # Test password change
        password_data = {'current_password': 'AnotherNewPass123', 'new_password': 'FinalTestPass123'}
        response = session.post(f'{base_url}/api/v1/password/change', json=password_data, headers=headers)
        total_tests += 1
        if response.status_code == 200:
            passed_tests += 1
            results['password_change'] = 'PASS'
            print('✅ Password Change: PASS')
        else:
            results['password_change'] = 'FAIL'
            print(f'❌ Password Change: FAIL - {response.status_code}')
    
    # 4. Password Reset
    print('\n4. PASSWORD RESET')
    print('-' * 30)
    
    reset_data = {'email': 'test@example.com'}
    response = session.post(f'{base_url}/api/v1/password/reset-request', json=reset_data)
    total_tests += 1
    if response.status_code == 200:
        passed_tests += 1
        results['password_reset'] = 'PASS'
        print('✅ Password Reset Request: PASS')
    else:
        results['password_reset'] = 'FAIL'
        print(f'❌ Password Reset Request: FAIL - {response.status_code}')
    
    # 5. Admin User Creation
    print('\n5. ADMIN USER CREATION')
    print('-' * 30)
    
    # Login as admin
    admin_login = {'username': 'test_admin_user', 'password': 'AdminPass123'}
    response = session.post(f'{base_url}/api/v1/login', json=admin_login)
    if response.status_code == 200:
        data = response.json()
        admin_token = data.get('access_token')
        admin_headers = {'Authorization': f'Bearer {admin_token}'}
        
        # Test admin user creation
        user_data = {'username': 'test_user_final', 'email': 'final@example.com', 'role': 'user', 'phone_number': '1234567890'}
        response = session.post(f'{base_url}/api/v1/admin/users/create', json=user_data, headers=admin_headers)
        total_tests += 1
        if response.status_code == 200:
            passed_tests += 1
            results['admin_create_user'] = 'PASS'
            print('✅ Admin Create User: PASS')
        else:
            results['admin_create_user'] = 'FAIL'
            print(f'❌ Admin Create User: FAIL - {response.status_code}')
    else:
        results['admin_create_user'] = 'FAIL'
        print(f'❌ Admin Login: FAIL - {response.status_code}')
    
    # Summary
    print('\n' + '=' * 60)
    print('📊 FINAL TEST SUMMARY')
    print('=' * 60)
    
    success_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0
    print(f'🎯 Overall Success Rate: {success_rate:.1f}% ({passed_tests}/{total_tests})')
    
    if success_rate >= 95:
        print('🎉 EXCELLENT: Auth and Users migration is PERFECT!')
    elif success_rate >= 85:
        print('✅ VERY GOOD: Auth and Users migration is working great!')
    elif success_rate >= 70:
        print('⚠️  GOOD: Most services working, minor issues to address')
    else:
        print('🚨 NEEDS ATTENTION: Multiple issues found')
    
    return results

if __name__ == "__main__":
    final_comprehensive_test()
