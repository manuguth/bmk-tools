from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tickets", "0009_ticketorder_collected_counts"),
    ]

    operations = [
        migrations.AddField(
            model_name="concert",
            name="capacity_show_numbers",
            field=models.BooleanField(
                default=True,
                verbose_name="Anzahl verbleibender Tickets anzeigen",
            ),
        ),
        migrations.AddField(
            model_name="concert",
            name="capacity_split_categories",
            field=models.BooleanField(
                default=True,
                verbose_name="Kategorien (Erwachsene/Kinder) getrennt anzeigen",
            ),
        ),
    ]
