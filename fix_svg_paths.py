import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'serverConfig.settings')
django.setup()

from api.models import Template

templates = Template.objects.all()
for t in templates:
    correct_path = f"templates/svgs/{t.id}.svg"
    print(f"Template: {t.name}")
    print(f"  Current svg_file.name: {t.svg_file.name}")
    print(f"  Correct path: {correct_path}")
    t.svg_file.name = correct_path
    Template.objects.filter(pk=t.pk).update(svg_file=correct_path)
    print(f"  -> Fixed to: {correct_path}")
    print()