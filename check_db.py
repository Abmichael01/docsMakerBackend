import os
import django
import sys

sys.path.append('/home/urkelcodes/Desktop/MyProjects/Clients/sharptoolz/backend')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'serverConfig.settings')
django.setup()

from analytics.models import VisitorLog, Campaign
from django.utils import timezone
from datetime import timedelta

today = timezone.localdate()
logs = VisitorLog.objects.filter(timestamp__date=today).order_by('-timestamp')

print(f"--- LOGS FOR {today} ---")
for l in logs:
    print(f"[{l.timestamp}] Path: {l.path}, Source: {l.source}, IsBot: {l.is_bot}, UID: {l.visitor_id}")

print("\n--- ALL CAMPAIGNS ---")
campaigns = Campaign.objects.all()
for c in campaigns:
    print(f"Name: {c.name}")
