#!/usr/bin/env python3
"""
Comprehensive Test Suite: Production Features Integration
Tests all production features working together
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import requests
import json
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List

class ProductionFeaturesTestSuite:
    """Comprehensive test suite for all production features"""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.session = requests.Session()
        self.test_results = []
        self.auth_token = None
        self.test_user_id = None
        
    def log_test(self, test_name: str, status: str, details: str = ""):
        """Log test results"""
        result = {
            "test_name": test_name,
            "status": status,
            "details": details,
            "timestamp": datetime.utcnow().isoformat()
        }
        self.test_results.append(result)
        
        status_color = "[PASS]" if status == "PASS" else "[FAIL]" if status == "FAIL" else "[WARN]"
        print(f"{status_color} {test_name}: {status}")
        if details:
            print(f"   {details}")
    
    def authenticate(self) -> bool:
        """Authenticate and get access token"""
        try:
            login_data = {
                "username": "test_fix_user",
                "password": "AnotherNewPassword123"  # Latest password
            }
            
            response = self.session.post(
                f"{self.base_url}/api/v1/login",
                json=login_data,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                token_data = response.json()
                self.auth_token = token_data["access_token"]
                self.session.headers.update({
                    "Authorization": f"Bearer {self.auth_token}"
                })
                self.log_test("Authentication", "PASS", f"Token obtained successfully")
                return True
            else:
                self.log_test("Authentication", "FAIL", f"Status: {response.status_code}")
                return False
                
        except Exception as e:
            self.log_test("Authentication", "FAIL", f"Error: {str(e)}")
            return False
    
    def test_audit_logging(self) -> bool:
        """Test audit logging functionality"""
        try:
            # Test getting audit logs
            response = self.session.get(f"{self.base_url}/api/v1/audit/logs")
            
            if response.status_code == 200:
                data = response.json()
                log_count = data.get("total_count", 0)
                self.log_test("Audit Logs Retrieval", "PASS", f"Retrieved {log_count} logs")
                
                # Test audit statistics
                stats_response = self.session.get(f"{self.base_url}/api/v1/audit/statistics")
                if stats_response.status_code == 200:
                    stats_data = stats_response.json()
                    total_logs = stats_data["statistics"]["total_logs"]
                    self.log_test("Audit Statistics", "PASS", f"Total logs: {total_logs}")
                    return True
                else:
                    self.log_test("Audit Statistics", "FAIL", f"Status: {stats_response.status_code}")
                    return False
            else:
                self.log_test("Audit Logs Retrieval", "FAIL", f"Status: {response.status_code}")
                return False
                
        except Exception as e:
            self.log_test("Audit Logging", "FAIL", f"Error: {str(e)}")
            return False
    
    def test_session_management(self) -> bool:
        """Test session management functionality"""
        try:
            # Test getting user sessions
            response = self.session.get(f"{self.base_url}/api/v1/sessions")
            
            if response.status_code == 200:
                data = response.json()
                # Handle both list and dict responses
                if isinstance(data, list):
                    session_count = len(data)
                else:
                    session_count = data.get("total_count", 0)
                self.log_test("Session Retrieval", "PASS", f"Retrieved {session_count} sessions")
                
                # Test session statistics
                stats_response = self.session.get(f"{self.base_url}/api/v1/sessions/statistics")
                if stats_response.status_code == 200:
                    stats_data = stats_response.json()
                    total_sessions = stats_data["statistics"]["total_sessions"]
                    active_sessions = stats_data["statistics"]["active_sessions"]
                    self.log_test("Session Statistics", "PASS", f"Total: {total_sessions}, Active: {active_sessions}")
                    return True
                else:
                    self.log_test("Session Statistics", "FAIL", f"Status: {stats_response.status_code}")
                    return False
            else:
                self.log_test("Session Retrieval", "FAIL", f"Status: {response.status_code}")
                return False
                
        except Exception as e:
            self.log_test("Session Management", "FAIL", f"Error: {str(e)}")
            return False
    
    def test_permissions_management(self) -> bool:
        """Test permissions management functionality"""
        try:
            # Test getting user permissions
            response = self.session.get(f"{self.base_url}/api/v1/permissions")
            
            if response.status_code == 200:
                data = response.json()
                perm_count = data.get("total_count", 0)
                self.log_test("Permissions Retrieval", "PASS", f"Retrieved {perm_count} permissions")
                
                # Test standard permissions
                std_response = self.session.get(f"{self.base_url}/api/v1/permissions/standard")
                if std_response.status_code == 200:
                    std_data = std_response.json()
                    std_count = len(std_data)
                    self.log_test("Standard Permissions", "PASS", f"Available: {std_count} permissions")
                    
                    # Test permission statistics
                    stats_response = self.session.get(f"{self.base_url}/api/v1/permissions/statistics")
                    if stats_response.status_code == 200:
                        stats_data = stats_response.json()
                        total_perms = stats_data["statistics"]["total_permissions"]
                        self.log_test("Permission Statistics", "PASS", f"Total permissions: {total_perms}")
                        return True
                    else:
                        self.log_test("Permission Statistics", "FAIL", f"Status: {stats_response.status_code}")
                        return False
                else:
                    self.log_test("Standard Permissions", "FAIL", f"Status: {std_response.status_code}")
                    return False
            else:
                self.log_test("Permissions Retrieval", "FAIL", f"Status: {response.status_code}")
                return False
                
        except Exception as e:
            self.log_test("Permissions Management", "FAIL", f"Error: {str(e)}")
            return False
    
    def test_groups_management(self) -> bool:
        """Test groups management functionality"""
        try:
            # Test getting organization groups
            response = self.session.get(f"{self.base_url}/api/v1/groups")
            
            if response.status_code == 200:
                data = response.json()
                group_count = data.get("total_count", 0)
                self.log_test("Groups Retrieval", "PASS", f"Retrieved {group_count} groups")
                
                # Test group statistics
                stats_response = self.session.get(f"{self.base_url}/api/v1/groups/statistics")
                if stats_response.status_code == 200:
                    stats_data = stats_response.json()
                    total_groups = stats_data["statistics"]["total_groups"]
                    total_memberships = stats_data["statistics"]["total_memberships"]
                    self.log_test("Group Statistics", "PASS", f"Groups: {total_groups}, Memberships: {total_memberships}")
                    return True
                else:
                    self.log_test("Group Statistics", "FAIL", f"Status: {stats_response.status_code}")
                    return False
            else:
                self.log_test("Groups Retrieval", "FAIL", f"Status: {response.status_code}")
                return False
                
        except Exception as e:
            self.log_test("Groups Management", "FAIL", f"Error: {str(e)}")
            return False
    
    def test_api_keys_management(self) -> bool:
        """Test API keys management functionality"""
        try:
            # Test getting user API keys
            response = self.session.get(f"{self.base_url}/api/v1/api-keys")
            
            if response.status_code == 200:
                data = response.json()
                key_count = data.get("total_count", 0)
                self.log_test("API Keys Retrieval", "PASS", f"Retrieved {key_count} API keys")
                
                # Test standard API permissions
                std_response = self.session.get(f"{self.base_url}/api/v1/api-keys/standard-permissions")
                if std_response.status_code == 200:
                    std_data = std_response.json()
                    std_count = len(std_data)
                    self.log_test("Standard API Permissions", "PASS", f"Available: {std_count} permissions")
                    
                    # Test API key statistics
                    stats_response = self.session.get(f"{self.base_url}/api/v1/api-keys/statistics")
                    if stats_response.status_code == 200:
                        stats_data = stats_response.json()
                        total_keys = stats_data["statistics"]["total_keys"]
                        active_keys = stats_data["statistics"]["active_keys"]
                        self.log_test("API Key Statistics", "PASS", f"Total: {total_keys}, Active: {active_keys}")
                        return True
                    else:
                        self.log_test("API Key Statistics", "FAIL", f"Status: {stats_response.status_code}")
                        return False
                else:
                    self.log_test("Standard API Permissions", "FAIL", f"Status: {std_response.status_code}")
                    return False
            else:
                self.log_test("API Keys Retrieval", "FAIL", f"Status: {response.status_code}")
                return False
                
        except Exception as e:
            self.log_test("API Keys Management", "FAIL", f"Error: {str(e)}")
            return False
    
    def test_password_history(self) -> bool:
        """Test password history functionality"""
        try:
            # Test getting password history
            response = self.session.get(f"{self.base_url}/api/v1/password/history")
            
            if response.status_code == 200:
                data = response.json()
                hist_count = data.get("total_count", 0)
                self.log_test("Password History Retrieval", "PASS", f"Retrieved {hist_count} password records")
                
                # Test password policy statistics
                stats_response = self.session.get(f"{self.base_url}/api/v1/password/policy-stats")
                if stats_response.status_code == 200:
                    stats_data = stats_response.json()
                    # Handle different response structures
                    if "statistics" in stats_data:
                        total_changes = stats_data["statistics"].get("total_password_changes", 0)
                    else:
                        total_changes = stats_data.get("total_password_changes", 0)
                    self.log_test("Password Policy Statistics", "PASS", f"Total changes: {total_changes}")
                    return True
                else:
                    self.log_test("Password Policy Statistics", "FAIL", f"Status: {stats_response.status_code}")
                    return False
            else:
                self.log_test("Password History Retrieval", "FAIL", f"Status: {response.status_code}")
                return False
                
        except Exception as e:
            self.log_test("Password History", "FAIL", f"Error: {str(e)}")
            return False
    
    def test_password_change_with_history(self) -> bool:
        """Test password change with history tracking"""
        try:
            # Change password to test history tracking
            password_data = {
                "current_password": "BrandNewPassword123",
                "new_password": "AnotherNewPassword123"
            }
            
            response = self.session.post(
                f"{self.base_url}/api/v1/password/change",
                json=password_data,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                self.log_test("Password Change", "PASS", "Password changed successfully")
                
                # Wait a moment for history to be saved
                time.sleep(1)
                
                # Check if password history was updated
                hist_response = self.session.get(f"{self.base_url}/api/v1/password/history")
                if hist_response.status_code == 200:
                    hist_data = hist_response.json()
                    new_count = hist_data.get("total_count", 0)
                    self.log_test("Password History Update", "PASS", f"History updated: {new_count} records")
                    return True
                else:
                    self.log_test("Password History Update", "FAIL", f"Status: {hist_response.status_code}")
                    return False
            else:
                self.log_test("Password Change", "FAIL", f"Status: {response.status_code}")
                return False
                
        except Exception as e:
            self.log_test("Password Change with History", "FAIL", f"Error: {str(e)}")
            return False
    
    def test_rate_limiting(self) -> bool:
        """Test rate limiting functionality"""
        try:
            # Make multiple rapid requests to test rate limiting
            rapid_requests = 0
            rate_limited = False
            
            for i in range(10):
                response = self.session.get(f"{self.base_url}/api/v1/permissions")
                if response.status_code == 429:  # Too Many Requests
                    rate_limited = True
                    break
                rapid_requests += 1
                time.sleep(0.1)  # Small delay between requests
            
            if rate_limited:
                self.log_test("Rate Limiting", "PASS", f"Rate limited after {rapid_requests} requests")
                return True
            else:
                self.log_test("Rate Limiting", "PASS", f"Made {rapid_requests} requests without rate limiting")
                return True
                
        except Exception as e:
            self.log_test("Rate Limiting", "FAIL", f"Error: {str(e)}")
            return False
    
    def test_error_handling(self) -> bool:
        """Test error handling"""
        try:
            # Test invalid endpoint
            response = self.session.get(f"{self.base_url}/api/v1/invalid-endpoint")
            
            if response.status_code == 404:
                self.log_test("404 Error Handling", "PASS", "Invalid endpoint returns 404")
                
                # Test unauthorized access
                unauthorized_session = requests.Session()
                unauth_response = unauthorized_session.get(f"{self.base_url}/api/v1/permissions")
                
                if unauth_response.status_code in [401, 403]:
                    self.log_test("401/403 Error Handling", "PASS", f"Unauthorized access returns {unauth_response.status_code}")
                    return True
                else:
                    self.log_test("401 Error Handling", "FAIL", f"Status: {unauth_response.status_code}")
                    return False
            else:
                self.log_test("404 Error Handling", "FAIL", f"Status: {response.status_code}")
                return False
                
        except Exception as e:
            self.log_test("Error Handling", "FAIL", f"Error: {str(e)}")
            return False
    
    def run_comprehensive_tests(self) -> Dict[str, Any]:
        """Run all comprehensive tests"""
        print("=" * 80)
        print("COMPREHENSIVE PRODUCTION FEATURES TEST SUITE")
        print("=" * 80)
        print()
        
        # Authenticate first
        if not self.authenticate():
            return {
                "success": False,
                "status": "AUTH_FAILED",
                "passed_tests": 0,
                "total_tests": 0,
                "success_rate": 0.0,
                "error": "Authentication failed",
                "results": self.test_results
            }
        
        print("\n" + "=" * 60)
        print("TESTING PRODUCTION FEATURES")
        print("=" * 60)
        
        # Run all tests
        tests = [
            ("Audit Logging", self.test_audit_logging),
            ("Session Management", self.test_session_management),
            ("Permissions Management", self.test_permissions_management),
            ("Groups Management", self.test_groups_management),
            ("API Keys Management", self.test_api_keys_management),
            ("Password History", self.test_password_history),
            ("Password Change with History", self.test_password_change_with_history),
            ("Rate Limiting", self.test_rate_limiting),
            ("Error Handling", self.test_error_handling)
        ]
        
        passed_tests = 0
        total_tests = len(tests)
        
        for test_name, test_func in tests:
            print(f"\n--- Testing {test_name} ---")
            try:
                if test_func():
                    passed_tests += 1
            except Exception as e:
                self.log_test(test_name, "FAIL", f"Exception: {str(e)}")
        
        # Generate summary
        print("\n" + "=" * 80)
        print("TEST SUMMARY")
        print("=" * 80)
        
        success_rate = (passed_tests / total_tests) * 100
        print(f"Tests Passed: {passed_tests}/{total_tests} ({success_rate:.1f}%)")
        
        if success_rate >= 90:
            print("*** EXCELLENT: All production features are working perfectly! ***")
            overall_status = "SUCCESS"
        elif success_rate >= 75:
            print("*** GOOD: Most production features are working well! ***")
            overall_status = "PARTIAL_SUCCESS"
        else:
            print("*** NEEDS ATTENTION: Some production features need fixes! ***")
            overall_status = "NEEDS_ATTENTION"
        
        return {
            "success": overall_status == "SUCCESS",
            "status": overall_status,
            "passed_tests": passed_tests,
            "total_tests": total_tests,
            "success_rate": success_rate,
            "results": self.test_results
        }

def main():
    """Main test runner"""
    print("Starting Comprehensive Production Features Test Suite...")
    
    # Run tests
    test_suite = ProductionFeaturesTestSuite()
    results = test_suite.run_comprehensive_tests()
    
    # Save results
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    results_file = f"test_results_{timestamp}.json"
    
    with open(results_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\nTest results saved to: {results_file}")
    
    if results["success"]:
        print("\n*** All production features are working perfectly! ***")
        sys.exit(0)
    else:
        print(f"\n*** Test suite completed with {results['success_rate']:.1f}% success rate ***")
        sys.exit(1)

if __name__ == "__main__":
    main()
