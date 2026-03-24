from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tickets", "0008_create_ticket_scanner_group"),
    ]

    operations = [
        migrations.AddField(
            model_name="ticketorder",
            name="collected_adult_count",
            field=models.PositiveIntegerField(
                blank=True, null=True, verbose_name="Abgeholt Erwachsene"
            ),
        ),
        migrations.AddField(
            model_name="ticketorder",
            name="collected_child_count",
            field=models.PositiveIntegerField(
                blank=True, null=True, verbose_name="Abgeholt Kinder"
            ),
        ),
    ]
