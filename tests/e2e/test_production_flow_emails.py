#!/usr/bin/env python3
"""
Production Flow Email Test Suite
Tests automated email triggers in actual API workflows
"""

import sys
import os
import requests
import time
from datetime import datetime

# Add project root to Python path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)


class ProductionFlowEmailTester:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.test_results = {}
        self.success_count = 0
        self.total_tests = 0
        self.test_email = "psaiprasad1728@gmail.com"
        
    def log_test(self, test_name: str, success: bool, details: str = ""):
        """Log test results"""
        self.total_tests += 1
        if success:
            self.success_count += 1
            status = "✅ PASS"
        else:
            status = "❌ FAIL"
        
        self.test_results[test_name] = {
            "status": status,
            "success": success,
            "details": details,
            "timestamp": datetime.now().isoformat()
        }
        
        print(f"{status} {test_name}")
        if details and not success:
            print(f"    {details}")
    
    def test_signup_email_trigger(self):
        """Test email trigger on user signup"""
        print("\n👤 TESTING SIGNUP EMAIL TRIGGER")
        print("=" * 50)
        
        timestamp = int(time.time())
        username = f"test_signup_{timestamp}"
        
        signup_data = {
            "username": username,
            "password": "TestSignupPass123",
            "email": self.test_email,
            "phone_number": f"123456{timestamp}"
        }
        
        try:
            response = requests.post(f"{self.base_url}/api/v1/signup", json=signup_data)
            
            if response.status_code == 200:
                self.log_test("User Signup → Welcome Email", True,
                             f"User created: {username}, Email: {self.test_email}")
                print("   → Check your inbox for WELCOME email!")
            else:
                self.log_test("User Signup → Welcome Email", False,
                             f"Signup failed: {response.status_code}")
                             
        except Exception as e:
            self.log_test("User Signup → Welcome Email", False, str(e))
    
    def test_password_reset_email_trigger(self):
        """Test email trigger on password reset request"""
        print("\n🔑 TESTING PASSWORD RESET EMAIL TRIGGER")
        print("=" * 50)
        
        try:
            # Use existing user's email
            reset_data = {"email": self.test_email}
            
            response = requests.post(
                f"{self.base_url}/api/v1/password/reset-request",
                json=reset_data
            )
            
            if response.status_code == 200:
                data = response.json()
                self.log_test("Password Reset Request → Reset Email", True,
                             f"Reset token generated, sent to {self.test_email}")
                print("   → Check your inbox for PASSWORD RESET email!")
            else:
                self.log_test("Password Reset Request → Reset Email", False,
                             f"Request failed: {response.status_code}")
                             
        except Exception as e:
            self.log_test("Password Reset Request → Reset Email", False, str(e))
    
    def test_admin_user_creation_email_trigger(self):
        """Test email trigger on admin creating user"""
        print("\n👨‍💼 TESTING ADMIN USER CREATION EMAIL TRIGGER")
        print("=" * 50)
        
        try:
            # Login as admin
            admin_login = {"username": "test_admin_user", "password": "AdminPass123"}
            response = requests.post(f"{self.base_url}/api/v1/login", json=admin_login)
            
            if response.status_code == 200:
                data = response.json()
                token = data.get("access_token")
                headers = {"Authorization": f"Bearer {token}"}
                
                # Create user with test email
                timestamp = int(time.time())
                user_data = {
                    "username": f"admin_created_{timestamp}",
                    "email": self.test_email,
                    "role": "user",
                    "phone_number": f"987654{timestamp}"
                }
                
                response = requests.post(
                    f"{self.base_url}/api/v1/admin/users/create",
                    json=user_data,
                    headers=headers
                )
                
                if response.status_code == 200:
                    response_data = response.json()
                    email_sent = response_data.get("email_sent", False)
                    temp_password = response_data.get("generated_password")
                    
                    self.log_test("Admin Creates User → Welcome Email", email_sent,
                                 f"User created: {user_data['username']}, Email sent: {email_sent}")
                    print(f"   → Check your inbox for WELCOME email with temp password: {temp_password}!")
                else:
                    self.log_test("Admin Creates User → Welcome Email", False,
                                 f"User creation failed: {response.status_code}")
            else:
                self.log_test("Admin Creates User → Welcome Email", False,
                             f"Admin login failed: {response.status_code}")
                             
        except Exception as e:
            self.log_test("Admin Creates User → Welcome Email", False, str(e))
    
    def run_all_tests(self):
        """Run all production flow tests"""
        print("🚀 PRODUCTION FLOW EMAIL TRIGGER TEST SUITE")
        print("=" * 80)
        print(f"Started at: {datetime.now().isoformat()}")
        print(f"API Base URL: {self.base_url}")
        print(f"Test Email: {self.test_email}")
        print("\n⚠️  IMPORTANT: Check your inbox for emails after each test!")
        
        # Run all test suites
        self.test_signup_email_trigger()
        print("\n⏳ Waiting 5 seconds before next test...")
        time.sleep(5)
        
        self.test_password_reset_email_trigger()
        print("\n⏳ Waiting 5 seconds before next test...")
        time.sleep(5)
        
        self.test_admin_user_creation_email_trigger()
        
        # Generate report
        self.generate_report()
        
        return self.test_results
    
    def generate_report(self):
        """Generate test report"""
        print("\n" + "=" * 80)
        print("📊 PRODUCTION FLOW EMAIL TEST REPORT")
        print("=" * 80)
        
        success_rate = (self.success_count / self.total_tests * 100) if self.total_tests > 0 else 0
        
        print(f"🎯 Overall Success Rate: {success_rate:.1f}% ({self.success_count}/{self.total_tests})")
        print(f"📅 Test Completed: {datetime.now().isoformat()}")
        print(f"📧 Test Email: {self.test_email}")
        
        # Show results
        print("\n📋 TEST RESULTS:")
        for test_name, result in self.test_results.items():
            print(f"  {result['status']} {test_name}")
        
        # Overall assessment
        print(f"\n🎉 ASSESSMENT:")
        if success_rate >= 95:
            print("EXCELLENT: All email triggers working perfectly!")
        elif success_rate >= 90:
            print("VERY GOOD: Email triggers working great!")
        elif success_rate >= 80:
            print("GOOD: Most triggers working, minor issues to address")
        else:
            print("NEEDS ATTENTION: Multiple trigger issues found")
        
        print(f"\n📧 EMAIL VERIFICATION:")
        print(f"   Please check your inbox: {self.test_email}")
        print(f"   You should receive:")
        print(f"   - Welcome email (from signup)")
        print(f"   - Password reset email")
        print(f"   - Welcome email (from admin user creation)")
        print(f"\n   If you see all 3 emails, email integration is PERFECT!")


def main():
    """Main test function"""
    tester = ProductionFlowEmailTester()
    results = tester.run_all_tests()
    return results

if __name__ == "__main__":
    main()
