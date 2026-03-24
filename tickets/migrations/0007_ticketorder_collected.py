from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tickets', '0006_concert_einlass'),
    ]

    operations = [
        migrations.AddField(
            model_name='ticketorder',
            name='collected',
            field=models.BooleanField(default=False, verbose_name='Abgeholt'),
        ),
    ]
