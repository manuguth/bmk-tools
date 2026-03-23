from django.db import migrations


def create_tickets_admin_group(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Group.objects.get_or_create(name="Tickets Admin")


def delete_tickets_admin_group(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Group.objects.filter(name="Tickets Admin").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("tickets", "0003_concert_color_fields"),
    ]

    operations = [
        migrations.RunPython(create_tickets_admin_group, delete_tickets_admin_group),
    ]
