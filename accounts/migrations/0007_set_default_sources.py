from django.db import migrations

def set_default_sources(apps, schema_editor):
    User = apps.get_model('accounts', 'User')
    User.objects.filter(source__isnull=True).update(source='Organic')

class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0006_user_source'),
    ]

    operations = [
        migrations.RunPython(set_default_sources),
    ]
