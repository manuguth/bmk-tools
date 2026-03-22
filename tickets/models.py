import random
import string

from django.db import models
from django.utils.text import slugify


class Concert(models.Model):
    name = models.CharField(max_length=255, verbose_name="Name")
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True, verbose_name="Beschreibung")
    date = models.DateTimeField(verbose_name="Datum & Uhrzeit")
    venue = models.CharField(max_length=255, verbose_name="Veranstaltungsort")
    adult_price = models.DecimalField(
        max_digits=6, decimal_places=2, verbose_name="Preis Erwachsene (€)"
    )
    child_price = models.DecimalField(
        max_digits=6, decimal_places=2, verbose_name="Preis Kinder bis 12 Jahre (€)"
    )
    max_adults = models.PositiveIntegerField(verbose_name="Max. Erwachsenen-Tickets")
    max_children = models.PositiveIntegerField(verbose_name="Max. Kinder-Tickets (bis 12 Jahre)")
    is_active = models.BooleanField(
        default=True, verbose_name="Aktiv (Vorverkauf offen)"
    )
    image = models.ImageField(
        upload_to="concert_posters/",
        blank=True,
        null=True,
        verbose_name="Konzertplakat (optional)",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["date"]
        verbose_name = "Konzert"
        verbose_name_plural = "Konzerte"

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    @property
    def adults_sold(self):
        result = self.orders.filter(
            status__in=["ausstehend", "bestaetigt"]
        ).aggregate(total=models.Sum("adult_count"))
        return result["total"] or 0

    @property
    def children_sold(self):
        result = self.orders.filter(
            status__in=["ausstehend", "bestaetigt"]
        ).aggregate(total=models.Sum("child_count"))
        return result["total"] or 0

    @property
    def adults_remaining(self):
        return max(0, self.max_adults - self.adults_sold)

    @property
    def children_remaining(self):
        return max(0, self.max_children - self.children_sold)

    @property
    def is_sold_out(self):
        return self.adults_remaining == 0 and self.children_remaining == 0


class TicketOrder(models.Model):
    STATUS_CHOICES = [
        ("ausstehend", "Ausstehend"),
        ("bestaetigt", "Bestätigt"),
        ("storniert", "Storniert"),
    ]

    concert = models.ForeignKey(
        Concert,
        on_delete=models.CASCADE,
        related_name="orders",
        verbose_name="Konzert",
    )
    customer_name = models.CharField(max_length=255, verbose_name="Name")
    customer_email = models.EmailField(verbose_name="E-Mail-Adresse")
    customer_phone = models.CharField(
        max_length=50, blank=True, verbose_name="Telefon (optional)"
    )
    adult_count = models.PositiveIntegerField(default=0, verbose_name="Anzahl Erwachsene")
    child_count = models.PositiveIntegerField(default=0, verbose_name="Anzahl Kinder")
    total_price = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        editable=False,
        verbose_name="Gesamtpreis (€)",
    )
    notes = models.TextField(blank=True, verbose_name="Anmerkungen (optional)")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Bestellt am")
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="ausstehend",
        verbose_name="Status",
    )
    confirmation_code = models.CharField(
        max_length=12,
        unique=True,
        editable=False,
        verbose_name="Bestätigungscode",
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Bestellung"
        verbose_name_plural = "Bestellungen"

    def __str__(self):
        return f"{self.customer_name} – {self.concert.name} ({self.confirmation_code})"

    @staticmethod
    def generate_confirmation_code():
        """Generate an 8-character unique alphanumeric confirmation code."""
        chars = string.ascii_uppercase + string.digits
        while True:
            code = "".join(random.choices(chars, k=8))
            if not TicketOrder.objects.filter(confirmation_code=code).exists():
                return code

    def save(self, *args, **kwargs):
        if not self.confirmation_code:
            self.confirmation_code = self.generate_confirmation_code()
        self.total_price = (
            self.adult_count * self.concert.adult_price
            + self.child_count * self.concert.child_price
        )
        super().save(*args, **kwargs)
