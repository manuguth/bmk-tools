from django.db import migrations, models

DEFAULT_EXCLUDED_NAMES = (
    "Vorstandssitzung",
    "Vorstände Exklusiv",
    "Besprechung Jugend",
    "Hauptversammlung MMV",
)


def seed_excluded_names(apps, schema_editor):
    NewsletterSettings = apps.get_model("info_mail", "NewsletterSettings")
    for obj in NewsletterSettings.objects.all():
        if not obj.excluded_appointment_names:
            obj.excluded_appointment_names = "\n".join(DEFAULT_EXCLUDED_NAMES)
            obj.save(update_fields=["excluded_appointment_names"])


class Migration(migrations.Migration):

    dependencies = [
        ("info_mail", "0006_weeklymail_reference_unique"),
    ]

    operations = [
        migrations.AddField(
            model_name="newslettersettings",
            name="excluded_appointment_names",
            field=models.TextField(
                blank=True,
                default="",
                help_text="Termine mit diesen Bezeichnungen werden aus dem Newsletter ausgeblendet. Eine Bezeichnung pro Zeile.",
                verbose_name="Ausgeschlossene Terminbezeichnungen",
            ),
        ),
        migrations.RunPython(seed_excluded_names, migrations.RunPython.noop),
    ]
