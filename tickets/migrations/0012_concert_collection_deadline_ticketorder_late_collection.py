from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tickets", "0011_ticketorder_paid"),
    ]

    operations = [
        migrations.AddField(
            model_name="concert",
            name="collection_deadline",
            field=models.TimeField(
                blank=True,
                null=True,
                verbose_name="Tickets abholen bis",
            ),
        ),
        migrations.AddField(
            model_name="ticketorder",
            name="late_collection",
            field=models.BooleanField(
                default=False,
                help_text="Markiert Bestellungen, bei denen der Kunde nach der Abholdeadline eintrifft. Diese Plätze werden nicht freigegeben.",
                verbose_name="Späte Abholung (nach Deadline)",
            ),
        ),
    ]
