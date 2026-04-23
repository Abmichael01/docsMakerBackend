import os
import django
import sys

sys.path.append('/home/urkelcodes/Desktop/MyProjects/Clients/sharptoolz/backend')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'serverConfig.settings')
django.setup()

from analytics.models import VisitorLog
deleted = VisitorLog.objects.filter(path__startswith='/api/').delete()
print(f"Deleted {deleted[0]} backend logs.")
