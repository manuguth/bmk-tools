# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("info_mail", "0005_add_default_test_email"),
    ]

    operations = [
        migrations.AlterField(
            model_name="weeklymails",
            name="reference",
            field=models.CharField(blank=True, max_length=255, unique=True),
        ),
    ]
