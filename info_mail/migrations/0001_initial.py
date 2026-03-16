# Generated migration for info_mail

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='WeeklyMails',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('week', models.IntegerField()),
                ('year', models.IntegerField()),
                ('reference', models.CharField(blank=True, max_length=255)),
                ('upload_date', models.DateTimeField()),
                ('html_file', models.FileField(blank=True, upload_to='html_files/')),
            ],
            options={
                'unique_together': {('week', 'year')},
            },
        ),
    ]
