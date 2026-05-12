import os
import django
import uuid
from django.core.files import File
from django.core.files.base import ContentFile

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'serverConfig.settings')
django.setup()

from api.models import Template, Tool

def create_template():
    try:
        f_path = 'media/templates/svgs/flight_itinerary_with_qr.svg'
        with open(f_path, 'r') as f:
            svg_content = f.read()
            
        t = Template(name='Flight Itinerary with QR v2')
        # Use the logic from models.py save() method
        t._raw_svg_data = svg_content
        t.save()
        print(f"Successfully created template: {t.name} (ID: {t.id})")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    create_template()
