from django.db import migrations


def create_ticket_scanner_group(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Group.objects.get_or_create(name="Ticket Scanner")


def delete_ticket_scanner_group(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Group.objects.filter(name="Ticket Scanner").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("tickets", "0007_ticketorder_collected"),
    ]

    operations = [
        migrations.RunPython(create_ticket_scanner_group, delete_ticket_scanner_group),
    ]
