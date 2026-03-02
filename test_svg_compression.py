import os
import sys
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "serverConfig.settings")
django.setup()

from api.models import Template

# Get the flight itinerary template
t = Template.objects.filter(name__icontains="Fligth Ideas").exclude(svg_file='')
t = Template.objects.filter(name="Fligth Iteneray").first()

if not t or not t.svg_file:
    print("Could not find any template with 'Fligth Iteneray'")
    sys.exit(1)

t.svg_file.open("rb")
db_bytes = t.svg_file.read()
t.svg_file.close()

try:
    with open("../frontend/public/test-svgs/flight-itinerary.svg", "rb") as f:
        local_bytes = f.read()
except FileNotFoundError:
    print("Could not find local file")
    sys.exit(1)

print(f"Template Name: {t.name}")
print(f"DB Length: {len(db_bytes)}")
print(f"Local Length: {len(local_bytes)}")

if len(db_bytes) == len(local_bytes):
    print("Same length!")
else:
    print("DIFFERENT LENGTH")

db_text = db_bytes.decode('utf-8')
local_text = local_bytes.decode('utf-8')

if db_text == local_text:
    print("Files are EXACTLY identical byte-for-byte!")
else:
    print("Files differ in content!")
