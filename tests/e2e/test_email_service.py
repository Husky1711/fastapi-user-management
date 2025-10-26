#!/usr/bin/env python3
"""
Comprehensive Email Service Test Suite
Tests all email templates and API integration scenarios
"""

import sys
import os
from datetime import datetime

# Add project root to Python path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from utils.email_service import get_email_service


class EmailServiceTester:
    def __init__(self):
        self.email_service = get_email_service()
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
    
    def test_verification_email(self):
        """Test email verification template"""
        print("\n📧 TESTING VERIFICATION EMAIL")
        print("=" * 40)
        
        try:
            result = self.email_service.send_verification_email(
                to_email=self.test_email,
                verification_token="test_token_12345",
                username="TestUser"
            )
            
            self.log_test("Verification Email", result, 
                         f"Sent to {self.test_email}")
                         
        except Exception as e:
            self.log_test("Verification Email", False, str(e))
    
    def test_password_reset_email(self):
        """Test password reset template"""
        print("\n🔑 TESTING PASSWORD RESET EMAIL")
        print("=" * 40)
        
        try:
            result = self.email_service.send_password_reset_email(
                to_email=self.test_email,
                reset_token="reset_token_12345",
                username="TestUser"
            )
            
            self.log_test("Password Reset Email", result,
                         f"Sent to {self.test_email}")
                         
        except Exception as e:
            self.log_test("Password Reset Email", False, str(e))
    
    def test_welcome_email(self):
        """Test welcome email template"""
        print("\n👋 TESTING WELCOME EMAIL")
        print("=" * 40)
        
        try:
            result = self.email_service.send_welcome_email(
                to_email=self.test_email,
                username="TestUser",
                temp_password="TestPass123"
            )
            
            self.log_test("Welcome Email", result,
                         f"Sent to {self.test_email}")
                         
        except Exception as e:
            self.log_test("Welcome Email", False, str(e))
    
    def test_welcome_email_without_password(self):
        """Test welcome email without temp password"""
        print("\n👋 TESTING WELCOME EMAIL (No Password)")
        print("=" * 40)
        
        try:
            result = self.email_service.send_welcome_email(
                to_email=self.test_email,
                username="TestUser2",
                temp_password=None
            )
            
            self.log_test("Welcome Email (No Password)", result,
                         f"Sent to {self.test_email}")
                         
        except Exception as e:
            self.log_test("Welcome Email (No Password)", False, str(e))
    
    def test_security_alert_email(self):
        """Test security alert template"""
        print("\n🔒 TESTING SECURITY ALERT EMAIL")
        print("=" * 40)
        
        try:
            result = self.email_service.send_security_alert_email(
                to_email=self.test_email,
                username="TestUser",
                alert_type="Login from new device",
                details="A login was detected from a new device. If this wasn't you, please secure your account."
            )
            
            self.log_test("Security Alert Email", result,
                         f"Sent to {self.test_email}")
                         
        except Exception as e:
            self.log_test("Security Alert Email", False, str(e))
    
    def test_different_alert_types(self):
        """Test different security alert types"""
        print("\n⚠️  TESTING DIFFERENT SECURITY ALERTS")
        print("=" * 40)
        
        alert_scenarios = [
            ("Failed Login Attempts", "Multiple failed login attempts detected. Account will be locked after 5 attempts."),
            ("Password Changed", "Your password has been changed successfully."),
            ("Session Revoked", "Your session has been revoked due to suspicious activity."),
            ("API Key Generated", "A new API key has been generated for your account."),
        ]
        
        for alert_type, details in alert_scenarios:
            try:
                result = self.email_service.send_security_alert_email(
                    to_email=self.test_email,
                    username="TestUser",
                    alert_type=alert_type,
                    details=details
                )
                
                self.log_test(f"Security Alert: {alert_type}", result,
                             f"Sent to {self.test_email}")
                             
            except Exception as e:
                self.log_test(f"Security Alert: {alert_type}", False, str(e))
    
    def test_html_email(self):
        """Test HTML email formatting"""
        print("\n🎨 TESTING HTML EMAIL FORMATTING")
        print("=" * 40)
        
        try:
            html_content = """
            <html>
                <body>
                    <h1 style="color: #4CAF50;">Test HTML Email</h1>
                    <p>This is a test email with HTML formatting.</p>
                    <ul>
                        <li>Bold: <strong>This is bold</strong></li>
                        <li>Italic: <em>This is italic</em></li>
                        <li>Link: <a href="https://example.com">Example Link</a></li>
                    </ul>
                </body>
            </html>
            """
            
            plain_text = "Test HTML Email\nThis is a test email."
            
            result = self.email_service.send_email(
                to_email=self.test_email,
                subject="HTML Email Test",
                html_content=html_content,
                plain_text_content=plain_text
            )
            
            self.log_test("HTML Email Formatting", result,
                         f"Sent to {self.test_email}")
                         
        except Exception as e:
            self.log_test("HTML Email Formatting", False, str(e))
    
    def run_all_tests(self):
        """Run all email tests"""
        print("🧪 COMPREHENSIVE EMAIL SERVICE TEST SUITE")
        print("=" * 80)
        print(f"Started at: {datetime.now().isoformat()}")
        print(f"Test Email: {self.test_email}")
        
        # Run all test suites
        self.test_verification_email()
        self.test_password_reset_email()
        self.test_welcome_email()
        self.test_welcome_email_without_password()
        self.test_security_alert_email()
        self.test_different_alert_types()
        self.test_html_email()
        
        # Generate report
        self.generate_report()
        
        return self.test_results
    
    def generate_report(self):
        """Generate test report"""
        print("\n" + "=" * 80)
        print("📊 EMAIL SERVICE TEST REPORT")
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
            print("EXCELLENT: All email templates working perfectly!")
        elif success_rate >= 90:
            print("VERY GOOD: Email service is working great!")
        elif success_rate >= 80:
            print("GOOD: Most emails working, minor issues to address")
        else:
            print("NEEDS ATTENTION: Multiple email issues found")
        
        print(f"\n💡 CHECK YOUR EMAIL:")
        print(f"   Check inbox at: {self.test_email}")
        print(f"   Look for test emails with subjects:")
        print(f"   - Verify Your Email Address")
        print(f"   - Password Reset Request")
        print(f"   - Welcome to FastAPI User Management System")
        print(f"   - Security Alert: ...")
        

def main():
    """Main test function"""
    tester = EmailServiceTester()
    results = tester.run_all_tests()
    return results

if __name__ == "__main__":
    main()
