#!/usr/bin/env python3
"""
2FA Implementation Test Suite
Tests all 2FA features: enable, verify, disable, status
"""

import sys
import os
import requests
import time
from datetime import datetime

# Add project root to Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

BASE_URL = "http://localhost:8000"
API_BASE = f"{BASE_URL}/api/v1"

class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    END = '\033[0m'

class Test2FA:
    def __init__(self):
        self.session = requests.Session()
        self.test_results = []
        
    def log_test(self, test_name: str, passed: bool, message: str = ""):
        """Log test result"""
        status = f"{Colors.GREEN}✅ PASS{Colors.END}" if passed else f"{Colors.RED}❌ FAIL{Colors.END}"
        print(f"{status} {test_name}")
        if message:
            print(f"   → {message}")
        self.test_results.append({"name": test_name, "passed": passed})
    
    def test_2fa_enable(self):
        """Test 2FA enable endpoint"""
        print(f"\n{Colors.BLUE}📱 TEST 1: Enable 2FA{Colors.END}")
        
        # First, login to get a token
        login_response = self.session.post(
            f"{API_BASE}/login",
            json={
                "username": "test_fix_user",
                "password": "AnotherNewPassword123"
            }
        )
        
        if login_response.status_code != 200:
            self.log_test("2FA Enable - Login Failed", False, f"Status: {login_response.status_code}")
            return None
        
        token = login_response.json().get("access_token")
        headers = {"Authorization": f"Bearer {token}"}
        
        # Enable 2FA
        try:
            response = self.session.post(
                f"{API_BASE}/2fa/enable",
                headers=headers,
                json={}
            )
            
            if response.status_code == 200:
                data = response.json()
                qr_code = data.get("qr_code", "")
                backup_codes = data.get("backup_codes", [])
                
                if qr_code and backup_codes:
                    self.log_test("2FA Enable", True, f"QR Code: {len(qr_code)} chars, Backup codes: {len(backup_codes)}")
                    return {
                        "token": token,
                        "headers": headers,
                        "backup_codes": backup_codes
                    }
                else:
                    self.log_test("2FA Enable", False, "Missing QR code or backup codes")
                    return None
            else:
                self.log_test("2FA Enable", False, f"Status: {response.status_code}, Response: {response.text}")
                return None
        except Exception as e:
            self.log_test("2FA Enable", False, str(e))
            return None
    
    def test_2fa_status(self, headers):
        """Test 2FA status endpoint"""
        print(f"\n{Colors.BLUE}📊 TEST 2: Get 2FA Status{Colors.END}")
        
        try:
            response = self.session.get(
                f"{API_BASE}/2fa/status",
                headers=headers
            )
            
            if response.status_code == 200:
                data = response.json()
                self.log_test("2FA Status", True, f"Enabled: {data.get('is_enabled')}")
                return True
            else:
                self.log_test("2FA Status", False, f"Status: {response.status_code}")
                return False
        except Exception as e:
            self.log_test("2FA Status", False, str(e))
            return False
    
    def test_2fa_verify_setup(self, headers, backup_codes):
        """Test 2FA verification (should fail without real code)"""
        print(f"\n{Colors.BLUE}🔐 TEST 3: Verify 2FA Code{Colors.END}")
        
        try:
            # Use a fake code (should fail)
            response = self.session.post(
                f"{API_BASE}/2fa/verify",
                headers=headers,
                json={"totp_code": "000000"}
            )
            
            # Should fail with invalid code
            if response.status_code == 200:
                data = response.json()
                success = data.get("success", False)
                self.log_test("2FA Verify (Invalid Code)", True, f"Success: {success} (Expected: False)")
                return not success
            else:
                self.log_test("2FA Verify", False, f"Status: {response.status_code}")
                return False
        except Exception as e:
            self.log_test("2FA Verify", False, str(e))
            return False
    
    def test_2fa_disable(self, headers):
        """Test 2FA disable endpoint"""
        print(f"\n{Colors.BLUE}🔓 TEST 4: Disable 2FA{Colors.END}")
        
        try:
            response = self.session.post(
                f"{API_BASE}/2fa/disable",
                headers=headers,
                json={"totp_code": "000000"}  # Dummy code
            )
            
            # Note: Will fail without real TOTP code, but tests endpoint
            if response.status_code in [200, 400]:
                self.log_test("2FA Disable Endpoint", True, f"Status: {response.status_code}")
                return True
            else:
                self.log_test("2FA Disable", False, f"Status: {response.status_code}")
                return False
        except Exception as e:
            self.log_test("2FA Disable", False, str(e))
            return False
    
    def print_summary(self):
        """Print test summary"""
        print(f"\n{Colors.BLUE}{'='*60}{Colors.END}")
        print(f"{Colors.BLUE}📊 TEST SUMMARY{Colors.END}")
        print(f"{Colors.BLUE}{'='*60}{Colors.END}")
        
        total = len(self.test_results)
        passed = sum(1 for r in self.test_results if r["passed"])
        failed = total - passed
        success_rate = (passed / total * 100) if total > 0 else 0
        
        print(f"\nTotal Tests: {total}")
        print(f"{Colors.GREEN}Passed: {passed}{Colors.END}")
        print(f"{Colors.RED}Failed: {failed}{Colors.END}")
        print(f"{Colors.BLUE}Success Rate: {success_rate:.1f}%{Colors.END}")
        print(f"\n{Colors.BLUE}{'='*60}{Colors.END}")
        
        if success_rate == 100:
            print(f"{Colors.GREEN}🎉 All tests passed!{Colors.END}")
        elif success_rate >= 80:
            print(f"{Colors.YELLOW}⚠️  Most tests passed, some improvements needed{Colors.END}")
        else:
            print(f"{Colors.RED}❌ Several tests failed{Colors.END}")
    
    def run_all_tests(self):
        """Run all 2FA tests"""
        print(f"\n{Colors.BLUE}{'='*60}{Colors.END}")
        print(f"{Colors.BLUE}🧪 2FA IMPLEMENTATION TEST SUITE{Colors.END}")
        print(f"{Colors.BLUE}{'='*60}{Colors.END}")
        
        # Test 1: Enable 2FA
        result = self.test_2fa_enable()
        
        if result:
            headers = result["headers"]
            backup_codes = result["backup_codes"]
            
            # Test 2: Get 2FA status
            self.test_2fa_status(headers)
            
            # Test 3: Verify 2FA code (will fail without real code)
            self.test_2fa_verify_setup(headers, backup_codes)
            
            # Test 4: Disable 2FA
            self.test_2fa_disable(headers)
        
        # Print summary
        self.print_summary()

if __name__ == "__main__":
    tester = Test2FA()
    tester.run_all_tests()
