"""
Locust Load Testing for Cenaris Compliance Management System

This file simulates real user behavior to test system performance under load.

Run locally:
    locust -f locustfile.py --host=http://localhost:5000

Run against Render:
    locust -f locustfile.py --host=https://your-app.onrender.com

Then open: http://localhost:8089
"""

from locust import HttpUser, task, between, SequentialTaskSet
import random
import json
from io import BytesIO
import re


class UserBehavior(SequentialTaskSet):
    """
    Simulates a typical user journey through the system.
    Tasks run in order (login -> dashboard -> actions -> logout)
    """
    
    def on_start(self):
        """Called when a simulated user starts"""
        # Test credentials - UPDATE THESE to match your test users
        self.test_users = [
            {"email": "test1@example.com", "password": "TestPassword123!"},
            {"email": "test2@example.com", "password": "TestPassword123!"},
            {"email": "test3@example.com", "password": "TestPassword123!"},
        ]
        self.user_data = random.choice(self.test_users)
        self.logged_in = False
    
    @task
    def login_user(self):
        """Task 1: User logs into the system"""
        # GET login page to extract CSRF token
        csrf_token = None
        with self.client.get("/auth/login", catch_response=True, name="Load Login Page") as response:
            if response.status_code == 200:
                # Extract CSRF token from the response
                match = re.search(r'name="csrf_token".*?value="([^"]+)"', response.text)
                if match:
                    csrf_token = match.group(1)
                response.success()
            else:
                response.failure(f"Login page failed: {response.status_code}")
                return
        
        if not csrf_token:
            print("Warning: Could not extract CSRF token, login may fail")
        
        # Simulate login form submission
        login_data = {
            "email": self.user_data["email"],
            "password": self.user_data["password"],
            "remember_me": False
        }
        
        # Add CSRF token if found
        if csrf_token:
            login_data["csrf_token"] = csrf_token
        
        with self.client.post(
            "/auth/login",
            data=login_data,
            catch_response=True,
            name="Submit Login"
        ) as response:
            if response.status_code in [200, 302]:  # 302 = redirect after login
                self.logged_in = True
                response.success()
            else:
                response.failure(f"Login failed: {response.status_code}")
                self.logged_in = False
    
    @task
    def view_dashboard(self):
        """Task 2: User views the main dashboard"""
        if not self.logged_in:
            return
        
        with self.client.get("/", catch_response=True, name="View Dashboard") as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Dashboard failed: {response.status_code}")
    
    @task
    def view_compliance_files(self):
        """Task 3: User browses compliance files"""
        if not self.logged_in:
            return
        
        with self.client.get("/main/compliance_files", catch_response=True, name="View Compliance Files") as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Compliance files failed: {response.status_code}")
    
    @task
    def view_departments(self):
        """Task 4: User views departments"""
        if not self.logged_in:
            return
        
        with self.client.get("/main/departments", catch_response=True, name="View Departments") as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Departments failed: {response.status_code}")
    
    @task
    def view_users_list(self):
        """Task 5: User views users list (admin action)"""
        if not self.logged_in:
            return
        
        with self.client.get("/main/users", catch_response=True, name="View Users List") as response:
            if response.status_code in [200, 403]:  # 403 if not admin
                response.success()
            else:
                response.failure(f"Users list failed: {response.status_code}")
    
    @task
    def simulate_file_upload(self):
        """Task 6: User uploads a compliance file (simulated)"""
        if not self.logged_in:
            return
        
        # GET upload page
        with self.client.get("/upload/", catch_response=True, name="Load Upload Page") as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Upload page failed: {response.status_code}")
        
        # Simulate small file upload (1KB test file)
        test_file_content = b"Test compliance data " * 50  # ~1KB
        files = {
            'file': ('test_compliance.csv', BytesIO(test_file_content), 'text/csv')
        }
        data = {
            'department': 'IT',
            'file_type': 'compliance_report'
        }
        
        with self.client.post(
            "/upload/upload_file",
            files=files,
            data=data,
            catch_response=True,
            name="Upload File"
        ) as response:
            if response.status_code in [200, 302, 400]:  # May fail validation, that's ok
                response.success()
            else:
                response.failure(f"Upload failed: {response.status_code}")
    
    @task
    def view_profile(self):
        """Task 7: User views their profile"""
        if not self.logged_in:
            return
        
        with self.client.get("/main/profile", catch_response=True, name="View Profile") as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Profile failed: {response.status_code}")
    
    @task
    def logout_user(self):
        """Task 8: User logs out"""
        if not self.logged_in:
            return
        
        with self.client.get("/auth/logout", catch_response=True, name="Logout") as response:
            if response.status_code in [200, 302]:
                self.logged_in = False
                response.success()
            else:
                response.failure(f"Logout failed: {response.status_code}")
        
        # Stop this user's task set (they'll restart from login)
        self.interrupt()


class BrowsingUser(HttpUser):
    """
    Simulates users who browse and interact with the system.
    
    Weight: Higher weight = more of these users in the test
    Wait time: Time between actions (simulates reading/thinking)
    """
    tasks = [UserBehavior]
    wait_time = between(2, 5)  # Wait 2-5 seconds between tasks
    weight = 3  # 75% of users are browsing users


class QuickUser(HttpUser):
    """
    Simulates quick users who just check dashboard and leave.
    These users perform fewer actions.
    """
    wait_time = between(1, 3)
    weight = 1  # 25% of users are quick users
    
    @task(3)
    def quick_login_and_dashboard(self):
        """Quick user: Just login and view dashboard"""
        # Login
        self.client.post("/auth/login", data={
            "email": "test1@example.com",
            "password": "TestPassword123!"
        }, name="Quick Login")
        
        # View dashboard
        self.client.get("/", name="Quick Dashboard View")
        
        # Logout
        self.client.get("/auth/logout", name="Quick Logout")
    
    @task(1)
    def view_public_pages(self):
        """Quick user: Browse public pages"""
        self.client.get("/auth/login", name="View Login Page")
        self.client.get("/main/privacy-policy", name="View Privacy Policy")


class AdminUser(HttpUser):
    """
    Simulates admin users performing management tasks.
    These users access admin-only features more frequently.
    """
    tasks = [UserBehavior]
    wait_time = between(3, 8)  # Admins spend more time on tasks
    weight = 1  # Small percentage of admin users
    
    def on_start(self):
        """Admin users use admin credentials"""
        self.test_admin = {
            "email": "admin@example.com",
            "password": "AdminPassword123!"
        }


# ============================================
# Custom Test Scenarios (Run separately)
# ============================================

class StressTestUser(HttpUser):
    """
    Aggressive stress testing - for finding breaking points.
    Use this separately: locust -f locustfile.py --user-class StressTestUser
    """
    wait_time = between(0.5, 1)  # Very fast
    
    @task
    def rapid_fire_requests(self):
        """Hammer the dashboard repeatedly"""
        self.client.get("/")
        self.client.get("/main/compliance_files")
        self.client.get("/main/departments")
