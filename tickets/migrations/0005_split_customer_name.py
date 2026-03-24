from django.db import migrations, models


def split_customer_name(apps, schema_editor):
    TicketOrder = apps.get_model("tickets", "TicketOrder")
    for order in TicketOrder.objects.all():
        parts = (order.customer_name or "").split(" ", 1)
        order.customer_firstname = parts[0]
        order.customer_lastname = parts[1] if len(parts) > 1 else ""
        order.save(update_fields=["customer_firstname", "customer_lastname"])


def reverse_split(apps, schema_editor):
    TicketOrder = apps.get_model("tickets", "TicketOrder")
    for order in TicketOrder.objects.all():
        order.customer_name = f"{order.customer_firstname} {order.customer_lastname}".strip()
        order.save(update_fields=["customer_name"])


class Migration(migrations.Migration):

    dependencies = [
        ("tickets", "0004_create_tickets_admin_group"),
    ]

    operations = [
        # Add new fields (nullable first to allow data migration)
        migrations.AddField(
            model_name="ticketorder",
            name="customer_firstname",
            field=models.CharField(max_length=150, verbose_name="Vorname", default=""),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="ticketorder",
            name="customer_lastname",
            field=models.CharField(max_length=150, verbose_name="Nachname", default=""),
            preserve_default=False,
        ),
        # Populate from existing customer_name
        migrations.RunPython(split_customer_name, reverse_code=reverse_split),
        # Remove old field
        migrations.RemoveField(
            model_name="ticketorder",
            name="customer_name",
        ),
    ]
