import requests
import json
import os
import sys

# Add backend to path so we can import django settings if needed, 
# but we'll just use requests against the local server.
BASE_URL = "http://localhost:8003/api"
ADMIN_USER = "verify_admin"
ADMIN_PASS = "AdminPass123!"

def setup_test_user():
    print(f"[*] Setting up test admin user: {ADMIN_USER}")
    # Using manage.py shell to ensure a clean test user exists
    cmd = f"python manage.py shell -c \"from accounts.models import User; User.objects.filter(username='{ADMIN_USER}').delete(); User.objects.create_superuser(username='{ADMIN_USER}', email='{ADMIN_USER}@test.com', password='{ADMIN_PASS}')\""
    os.system(cmd)

def test_endpoint(name, method, path, data=None, headers=None, expected_status=200):
    url = f"{BASE_URL}{path}"
    print(f"[*] Testing {name}: {method} {path}...", end=" ", flush=True)
    try:
        if method == "GET":
            response = requests.get(url, headers=headers, params=data)
        elif method == "POST":
            response = requests.post(url, headers=headers, json=data)
        
        if response.status_code == expected_status:
            print("[\033[92mOK\033[0m]")
            return response.json()
        else:
            print(f"[\033[91mFAILED\033[0m] (Status: {response.status_code})")
            print(f"    Error: {response.text[:200]}")
            return None
    except Exception as e:
        print(f"[\033[91mERROR\033[0m] ({str(e)})")
        return None

def run_tests():
    setup_test_user()
    
    # 1. Login
    print("[*] Authenticating...")
    login_url = f"{BASE_URL}/accounts/login/"
    session = requests.Session()
    login_res = session.post(login_url, json={"username": ADMIN_USER, "password": ADMIN_PASS})
    
    if login_res.status_code != 200:
        print("[!] Login failed. Is the server running on http://localhost:8003?")
        return

    print("[*] Authentication successful.")
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    
    # List of endpoints to test
    endpoints = [
        ("Dashboard Stats", "GET", "/analytics/dashboard/"),
        ("Campaign Stats", "GET", "/analytics/campaigns/stats/"),
        ("Campaign List", "GET", "/analytics/campaigns/"),
        ("User Activity", "GET", "/analytics/user-activity/"),
        ("Audit Logs", "GET", "/analytics/audit-logs/"),
    ]

    for name, method, path in endpoints:
        test_endpoint(name, method, path, headers=headers)

    # Test Public endpoint
    test_endpoint("Public Log Visit", "POST", "/analytics/log-visit/", data={"path": "/test/path"})

if __name__ == "__main__":
    run_tests()
