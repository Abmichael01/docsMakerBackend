from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0021_remove_template_api_templat_is_acti_978198_idx_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="purchasedtemplate",
            name="keywords",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="template",
            name="keywords",
            field=models.JSONField(blank=True, default=list),
        ),
    ]


