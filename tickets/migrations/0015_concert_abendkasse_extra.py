from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tickets', '0014_ticketorder_source_order'),
    ]

    operations = [
        migrations.AddField(
            model_name='concert',
            name='abendkasse_extra_adults',
            field=models.PositiveIntegerField(
                default=0,
                help_text='Zusätzliche Plätze für den Direktverkauf an der Abendkasse (gilt nicht für den Online-Vorverkauf).',
                verbose_name='Extra Abendkasse-Tickets Erwachsene',
            ),
        ),
        migrations.AddField(
            model_name='concert',
            name='abendkasse_extra_children',
            field=models.PositiveIntegerField(
                default=0,
                help_text='Zusätzliche Kinder-Plätze für den Direktverkauf an der Abendkasse (gilt nicht für den Online-Vorverkauf).',
                verbose_name='Extra Abendkasse-Tickets Kinder',
            ),
        ),
    ]
