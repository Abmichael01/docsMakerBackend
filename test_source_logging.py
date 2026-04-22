import os
import django
import sys

# Set up Django environment
sys.path.append('/home/urkelcodes/Desktop/MyProjects/Clients/sharptoolz/backend')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'serverConfig.settings')
django.setup()

from analytics.models import VisitorLog
from django.utils import timezone

def test_source_logging(source_name):
    print(f"Testing logging for source: {source_name}")
    
    # Simulate a log entry
    log = VisitorLog.objects.create(
        ip_address="127.0.0.1",
        path="/test-path",
        method="GET",
        source=source_name,
        timestamp=timezone.now()
    )
    print(f"Created log ID: {log.id} with source: {log.source}")
    
    # Verify it exists
    verified = VisitorLog.objects.filter(source=source_name).latest('timestamp')
    print(f"Verification: Found log with source {verified.source}")
    
    if verified.source == source_name:
        print("SUCCESS: Source logic is working in the database.")
    else:
        print("FAILURE: Source mismatch.")

if __name__ == "__main__":
    test_source_logging("Verification_Test_Campaign")
