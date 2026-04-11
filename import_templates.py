import os
import sys
import django

# Setup Django environment
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'serverConfig.settings')
django.setup()

from api.models import Template

# Directory containing SVGs relative to backend
templates_dir = '../templates'

if not os.path.exists(templates_dir):
    print(f"Error: {templates_dir} does not exist.")
    sys.exit(1)

svg_files = [f for f in os.listdir(templates_dir) if f.endswith('.svg')]
print(f"Found {len(svg_files)} SVGs to import.")

for svg_filename in svg_files:
    file_path = os.path.join(templates_dir, svg_filename)
    template_name = svg_filename.replace('.svg', '')
    
    with open(file_path, 'r', encoding='utf-8') as f:
        raw_svg = f.read()

    # Get or create template
    template, created = Template.objects.get_or_create(
        name=template_name,
        defaults={'type': 'design'}
    )
    
    # Passing the raw SVG triggers ID fixing and form field parsing inside .save()
    setattr(template, '_raw_svg_data', raw_svg)
    
    try:
        template.save()
        status = "Created" if created else "Updated"
        print(f"✅ [{status}] Template '{template_name}' - {len(template.form_fields)} fields parsed.")
    except Exception as e:
        print(f"❌ Failed to process '{template_name}': {str(e)}")

print("\nTemplate creation process complete!")
