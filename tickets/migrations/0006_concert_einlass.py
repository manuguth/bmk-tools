from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tickets', '0005_split_customer_name'),
    ]

    operations = [
        migrations.AddField(
            model_name='concert',
            name='einlass',
            field=models.TimeField(blank=True, null=True, verbose_name='Einlass'),
        ),
    ]
