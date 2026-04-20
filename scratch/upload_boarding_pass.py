import os
import django
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage

# Setup Django environment
import sys
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'serverConfig.settings')
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
django.setup()

from api.models import Template, Tool

# Paths
fixed_svg_path = '/home/urkelcodes/Desktop/MyProjects/Clients/sharptoolz/templates/Boarding Pass1_Fixed.svg'
target_svg_name = 'templates/svgs/boarding_pass_test.svg'

def upload():
    # 1. Read fixed SVG
    if not os.path.exists(fixed_svg_path):
        print(f"Error: {fixed_svg_path} not found")
        return

    with open(fixed_svg_path, 'r', encoding='utf-8') as f:
        svg_content = f.read()

    # 2. Get or create Tool
    tool, created = Tool.objects.get_or_create(
        name="Boarding Pass",
        defaults={
            "description": "Boarding Pass Tool for testing",
            "price": 5.00,
            "is_active": True
        }
    )
    if created:
        print(f"Created Tool: {tool.name}")
    else:
        print(f"Using existing Tool: {tool.name}")

    # 3. Create Template
    # We'll use a fixed ID for easy tracking or let Django create one
    template_name = "Boarding Pass Test"
    template = Template.objects.filter(name=template_name).first()
    
    if not template:
        template = Template(
            name=template_name,
            type='tool',
            tool=tool,
            is_active=True
        )
        print(f"Creating new Template: {template_name}")
    else:
        print(f"Updating existing Template: {template_name}")

    # 4. Save SVG file and trigger re-parse
    # We set _raw_svg_data so the save() method handles parsing and file storage
    setattr(template, '_raw_svg_data', svg_content)
    template.save()

    print(f"Successfully uploaded and parsed template: {template.name}")
    print(f"File path: {template.svg_file.name}")
    print(f"Form fields count: {len(template.form_fields)}")

if __name__ == "__main__":
    upload()
