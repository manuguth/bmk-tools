from django.db import models
import random
import string

def generate_hash_value():
    letters = string.ascii_letters
    random_letters = ''.join(random.choice(letters) for _ in range(8))
    return random_letters.lower()


class NewsletterSettings(models.Model):
    """Singleton model for newsletter configuration — editable via Django Admin."""
    recipient = models.EmailField(
        default="hauptkapelle@bmk-buggingen.de",
        verbose_name="Empfänger",
        help_text="E-Mail-Adresse oder Verteiler für den regulären Versand",
    )
    from_email = models.EmailField(
        default="news@bmk-buggingen.de",
        verbose_name="Absender",
    )
    km_appointments_url = models.URLField(
        max_length=500,
        blank=True,
        verbose_name="Konzertmeister Termine-URL",
    )
    km_requests_url = models.URLField(
        max_length=500,
        blank=True,
        verbose_name="Konzertmeister Anfragen-URL",
    )
    mmv_newsletter_url = models.URLField(
        max_length=500,
        blank=True,
        verbose_name="MMV Newsletter-URL",
        help_text="Monatlich wechselnder Brevo-Link zum aktuellen MMV-Newsletter",
    )
    mmv_newsletter_month = models.CharField(
        max_length=20,
        blank=True,
        verbose_name="MMV Newsletter Monat",
        help_text='Anzeigename des aktuellen MMV-Newsletter-Monats, z. B. "März" oder "April"',
    )
    default_test_email = models.EmailField(
        blank=True,
        verbose_name="Standard Test-Versand E-Mail",
        help_text="Wird im Compose-Bereich als Vorbelegung für den Test-Versand angezeigt.",
    )

    class Meta:
        verbose_name = "Newsletter-Einstellung"
        verbose_name_plural = "Newsletter-Einstellungen"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def get_settings(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def __str__(self):
        return "Newsletter-Einstellungen"


class WeeklyMails(models.Model):
    STATUS_CHOICES = [
        ("draft", "Entwurf"),
        ("sent", "Gesendet"),
    ]

    week = models.IntegerField()
    year = models.IntegerField()

    class Meta:
        unique_together = ('week', 'year')
    reference = models.CharField(max_length=255, blank=True)
    status = models.CharField(
        max_length=10, choices=STATUS_CHOICES, default="draft",
        verbose_name="Status",
    )

    # Section content fields
    intro = models.TextField(blank=True, verbose_name="Intro")
    info_content = models.TextField(blank=True, verbose_name="Infos")
    events = models.TextField(blank=True, verbose_name="Veranstaltungen")
    konzert = models.TextField(blank=True, verbose_name="Konzert")
    sonstiges = models.TextField(blank=True, verbose_name="Sonstiges")

    def save(self, *args, **kwargs):
        if not self.reference:
            # Generate hash value
            self.reference = generate_hash_value()
        super().save(*args, **kwargs)
    upload_date = models.DateTimeField(auto_now=True)
    html_file = models.FileField(upload_to='html_files/', blank=True)
