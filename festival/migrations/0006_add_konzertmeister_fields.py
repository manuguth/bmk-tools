# Generated migration for Konzertmeister integration

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('festival', '0005_tasktemplate'),
    ]

    operations = [
        migrations.AddField(
            model_name='task',
            name='konzertmeister_event_id',
            field=models.IntegerField(null=True, blank=True),
        ),
        migrations.AddField(
            model_name='participant',
            name='konzertmeister_user_id',
            field=models.IntegerField(null=True, blank=True),
        ),
        migrations.AddField(
            model_name='participant',
            name='konzertmeister_response_status',
            field=models.CharField(
                max_length=20,
                choices=[('unknown', 'Unknown'), ('positive', 'Positive'), ('maybe', 'Maybe')],
                default='unknown',
            ),
        ),
    ]
