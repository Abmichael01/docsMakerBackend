import os
import django
from django.test import Client
from django.contrib.auth import get_user_model

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'serverConfig.settings')
django.setup()

User = get_user_model()

def run_internal_tests():
    print("[*] Starting internal endpoint verification...")
    
    # Setup Admin
    admin_username = "verify_admin_internal"
    User.objects.filter(username=admin_username).delete()
    admin = User.objects.create_superuser(
        username=admin_username, 
        email=f"{admin_username}@test.com", 
        password="AdminPass123!"
    )
    
    client = Client()
    client.force_login(admin)
    
    endpoints = [
        ("Analytics Dashboard", "/api/analytics/dashboard/"),
        ("Campaign Stats", "/api/analytics/campaigns/stats/"),
        ("Campaign List", "/api/analytics/campaigns/"),
        ("User Activity", "/api/analytics/user-activity/"),
        ("Audit Logs", "/api/analytics/audit-logs/"),
    ]
    
    results = []
    for name, path in endpoints:
        print(f"[*] Testing {name} ({path})...", end=" ", flush=True)
        try:
            response = client.get(path)
            if response.status_code == 200:
                print("[\033[92mOK\033[0m]")
                results.append(True)
            else:
                print(f"[\033[91mFAILED\033[0m] (Status: {response.status_code})")
                print(f"    {response.content[:200]}")
                results.append(False)
        except Exception as e:
            print(f"[\033[91mERROR\033[0m] ({str(e)})")
            results.append(False)
            
    # Cleanup
    admin.delete()
    
    if all(results):
        print("\n[+] \033[92mAll internal endpoints verified successfully!\033[0m")
    else:
        print("\n[!] \033[91mSome endpoints failed verification.\033[0m")
        sys.exit(1)

if __name__ == "__main__":
    import sys
    run_internal_tests()
