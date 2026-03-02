import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'serverConfig.settings')
django.setup()

from django.core.files.base import ContentFile
from api.models import Template

t = Template.objects.filter(name='Fligth Iteneray').first()
print('BEFORE:', t.svg_file.name)
t.svg_file.save(f'{t.id}.svg', ContentFile(b'test'), save=False)
print('AFTER:', t.svg_file.name)
