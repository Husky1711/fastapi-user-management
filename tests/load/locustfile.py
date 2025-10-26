"""
Load Testing for FastAPI User Management System
Using Locust for performance testing
"""

from locust import HttpUser, task, between
import json


class UserManagementUser(HttpUser):
    """
    Simulate a regular user accessing the system
    """
    wait_time = between(1, 3)  # Wait 1-3 seconds between requests
    weight = 3  # 3x more common than admin
    
    def on_start(self):
        """Login when user starts"""
        # Try to login as regular user
        response = self.client.post("/api/v1/login", json={
            "username": "test_auth_user",
            "password": "NewSecurePass123"
        }, name="User Login")
        
        if response.status_code == 200:
            data = response.json()
            self.token = data.get("access_token")
            self.headers = {"Authorization": f"Bearer {self.token}"}
        else:
            # If login fails, just proceed without token
            self.token = None
            self.headers = {}
    
    @task(3)
    def view_profile(self):
        """View user profile (most common)"""
        if self.token:
            self.client.get("/api/v1/profile", headers=self.headers, name="User Profile")
    
    @task(2)
    def view_dashboard_overview(self):
        """View user dashboard overview"""
        if self.token:
            self.client.get("/api/v1/dashboard/user/overview", headers=self.headers, name="User Dashboard")
    
    @task(2)
    def view_dashboard_activity(self):
        """View activity dashboard"""
        if self.token:
            self.client.get("/api/v1/dashboard/user/activity", headers=self.headers, name="User Activity")
    
    @task(1)
    def view_dashboard_sessions(self):
        """View sessions"""
        if self.token:
            self.client.get("/api/v1/dashboard/user/sessions", headers=self.headers, name="User Sessions")


class AdminUser(HttpUser):
    """
    Simulate an admin user
    """
    wait_time = between(2, 4)  # Admins wait longer between requests
    weight = 2  # 2x more common than super admin
    
    def on_start(self):
        """Login as admin"""
        response = self.client.post("/api/v1/login", json={
            "username": "test_dashboard_admin",
            "password": "TestDashboardPass123!"
        }, name="Admin Login")
        
        if response.status_code == 200:
            data = response.json()
            self.token = data.get("access_token")
            self.headers = {"Authorization": f"Bearer {self.token}"}
        else:
            self.token = None
            self.headers = {}
    
    @task(3)
    def admin_overview(self):
        """Admin dashboard overview"""
        if self.token:
            self.client.get("/api/v1/dashboard/admin/overview", headers=self.headers, name="Admin Overview")
    
    @task(2)
    def admin_users_stats(self):
        """Admin users stats"""
        if self.token:
            self.client.get("/api/v1/dashboard/admin/users/stats", headers=self.headers, name="Admin Users Stats")
    
    @task(1)
    def admin_activity_stats(self):
        """Admin activity stats"""
        if self.token:
            self.client.get("/api/v1/dashboard/admin/activity/stats", headers=self.headers, name="Admin Activity Stats")


class SuperAdminUser(HttpUser):
    """
    Simulate a super admin (rare)
    """
    wait_time = between(3, 6)  # Super admins are less frequent
    weight = 1  # Rarest
    
    def on_start(self):
        """Login as super admin"""
        response = self.client.post("/api/v1/login", json={
            "username": "test_super_admin",
            "password": "TestSuperAdminPass123!"
        }, name="Super Admin Login")
        
        if response.status_code == 200:
            data = response.json()
            self.token = data.get("access_token")
            self.headers = {"Authorization": f"Bearer {self.token}"}
        else:
            self.token = None
            self.headers = {}
    
    @task(3)
    def super_admin_overview(self):
        """Super admin overview"""
        if self.token:
            self.client.get("/api/v1/dashboard/super-admin/overview", headers=self.headers, name="Super Admin Overview")
    
    @task(2)
    def super_admin_users_stats(self):
        """Super admin users stats"""
        if self.token:
            self.client.get("/api/v1/dashboard/super-admin/users/stats", headers=self.headers, name="Super Admin Users Stats")
    
    @task(1)
    def super_admin_orgs_stats(self):
        """Super admin organizations stats"""
        if self.token:
            self.client.get("/api/v1/dashboard/super-admin/organizations/stats", headers=self.headers, name="Super Admin Orgs Stats")

