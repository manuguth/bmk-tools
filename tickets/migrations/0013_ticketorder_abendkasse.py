from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tickets", "0012_concert_collection_deadline_ticketorder_late_collection"),
    ]

    operations = [
        migrations.AddField(
            model_name="ticketorder",
            name="abendkasse",
            field=models.BooleanField(
                default=False,
                help_text="Gibt an, ob das Ticket an der Abendkasse verkauft wurde.",
                verbose_name="Abendkasse",
            ),
        ),
    ]
