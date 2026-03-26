from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('festival', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='participant',
            name='pinned',
            field=models.BooleanField(default=False),
        ),
    ]
