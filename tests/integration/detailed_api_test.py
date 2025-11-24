#!/usr/bin/env python3
"""
Detailed API Testing Script
"""

import requests
import json

from tests.config import API_BASE_URL

def test_all_apis():
    base_url = API_BASE_URL
    session = requests.Session()
    
    print('🔍 DETAILED API TESTING')
    print('=' * 50)
    
    # 1. Test login
    print('\n1. Testing Login...')
    login_data = {'username': 'test_auth_user', 'password': 'NewTestPass123'}
    response = session.post(f'{base_url}/api/v1/login', json=login_data)
    print(f'Login: {response.status_code} - {"PASS" if response.status_code == 200 else "FAIL"}')
    
    if response.status_code != 200:
        print(f'Login failed: {response.text}')
        return
    
    data = response.json()
    token = data.get('access_token')
    refresh_token = data.get('refresh_token')
    
    # 2. Test refresh token
    print('\n2. Testing Refresh Token...')
    refresh_data = {'refresh_token': refresh_token}
    response = session.post(f'{base_url}/api/v1/refresh', json=refresh_data)
    print(f'Refresh: {response.status_code} - {"PASS" if response.status_code == 200 else "FAIL"}')
    if response.status_code != 200:
        print(f'Refresh failed: {response.text}')
    
    # 3. Test logout
    print('\n3. Testing Logout...')
    logout_data = {'refresh_token': refresh_token}
    response = session.post(f'{base_url}/api/v1/logout', json=logout_data)
    print(f'Logout: {response.status_code} - {"PASS" if response.status_code == 200 else "FAIL"}')
    if response.status_code != 200:
        print(f'Logout failed: {response.text}')
    
    # 4. Test authenticated endpoints
    print('\n4. Testing Authenticated Endpoints...')
    headers = {'Authorization': f'Bearer {token}'}
    
    endpoints = [
        '/api/v1/profile',
        '/api/v1/users', 
        '/api/v1/sessions',
        '/api/v1/password/history'
    ]
    
    for endpoint in endpoints:
        response = session.get(f'{base_url}{endpoint}', headers=headers)
        print(f'{endpoint}: {response.status_code} - {"PASS" if response.status_code == 200 else "FAIL"}')
        if response.status_code != 200:
            print(f'  Error: {response.text[:100]}...')
    
    # 5. Test password change
    print('\n5. Testing Password Change...')
    password_data = {'current_password': 'NewTestPass123', 'new_password': 'AnotherNewPass123'}
    response = session.post(f'{base_url}/api/v1/password/change', json=password_data, headers=headers)
    print(f'Password Change: {response.status_code} - {"PASS" if response.status_code == 200 else "FAIL"}')
    if response.status_code != 200:
        print(f'Password change failed: {response.text}')
    
    # 6. Test password reset
    print('\n6. Testing Password Reset...')
    reset_data = {'email': 'test@example.com'}
    response = session.post(f'{base_url}/api/v1/password/reset-request', json=reset_data)
    print(f'Password Reset Request: {response.status_code} - {"PASS" if response.status_code == 200 else "FAIL"}')
    if response.status_code != 200:
        print(f'Password reset failed: {response.text}')
    
    # 7. Test enhanced login
    print('\n7. Testing Enhanced Login...')
    strategies = ['allow_multiple', 'replace_all', 'replace_same_device', 'limit_sessions']
    for strategy in strategies:
        response = session.post(f'{base_url}/api/v1/login-with-session-control?session_strategy={strategy}', json=login_data)
        print(f'Enhanced Login ({strategy}): {response.status_code} - {"PASS" if response.status_code == 200 else "FAIL"}')
        if response.status_code != 200:
            print(f'  Error: {response.text[:100]}...')
    
    print('\n✅ Detailed testing complete!')

if __name__ == "__main__":
    test_all_apis()
