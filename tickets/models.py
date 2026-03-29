import random
import string

from django.core.validators import RegexValidator
from django.db import models
from django.db.models.functions import Least
from django.utils.text import slugify

_hex_validator = RegexValidator(
    regex=r'^#[0-9A-Fa-f]{6}$',
    message='Geben Sie eine gültige Hex-Farbe ein (z.B. #0d1b2a).'
)


class Concert(models.Model):
    name = models.CharField(max_length=255, verbose_name="Name")
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True, verbose_name="Beschreibung")
    date = models.DateTimeField(verbose_name="Datum & Uhrzeit")
    einlass = models.TimeField(
        null=True,
        blank=True,
        verbose_name="Einlass",
    )
    collection_deadline = models.TimeField(
        null=True,
        blank=True,
        verbose_name="Tickets abholen bis",
    )
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
    color_primary = models.CharField(
        max_length=7,
        default='#0d1b2a',
        validators=[_hex_validator],
        verbose_name='Primärfarbe',
    )
    color_accent = models.CharField(
        max_length=7,
        default='#c9a84c',
        validators=[_hex_validator],
        verbose_name='Akzentfarbe',
    )
    color_background = models.CharField(
        max_length=7,
        default='#f5f0e8',
        validators=[_hex_validator],
        verbose_name='Hintergrundfarbe',
    )
    capacity_show_numbers = models.BooleanField(
        default=True,
        verbose_name='Anzahl verbleibender Tickets anzeigen',
    )
    capacity_split_categories = models.BooleanField(
        default=True,
        verbose_name='Kategorien (Erwachsene/Kinder) getrennt anzeigen',
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
        # Collected orders count only actual attendees; uncollected orders still hold their reservation.
        # collected_adult_count is capped at adult_count so extras stored for display don't
        # double-count with the separate Abendkasse order that is created for those extras.
        result = self.orders.filter(
            status__in=["ausstehend", "bestaetigt"]
        ).aggregate(
            total=models.Sum(
                models.Case(
                    models.When(
                        collected=True,
                        collected_adult_count__isnull=False,
                        then=Least(models.F("collected_adult_count"), models.F("adult_count")),
                    ),
                    default=models.F("adult_count"),
                    output_field=models.IntegerField(),
                )
            )
        )
        return result["total"] or 0

    @property
    def children_sold(self):
        result = self.orders.filter(
            status__in=["ausstehend", "bestaetigt"]
        ).aggregate(
            total=models.Sum(
                models.Case(
                    models.When(
                        collected=True,
                        collected_child_count__isnull=False,
                        then=Least(models.F("collected_child_count"), models.F("child_count")),
                    ),
                    default=models.F("child_count"),
                    output_field=models.IntegerField(),
                )
            )
        )
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
    customer_firstname = models.CharField(max_length=150, verbose_name="Vorname")
    customer_lastname = models.CharField(max_length=150, verbose_name="Nachname")
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
    collected = models.BooleanField(
        default=False,
        verbose_name="Abgeholt",
    )
    collected_adult_count = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Abgeholt Erwachsene",
    )
    collected_child_count = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Abgeholt Kinder",
    )
    paid = models.BooleanField(
        default=False,
        verbose_name="Bezahlt",
    )
    abendkasse = models.BooleanField(
        default=False,
        verbose_name="Abendkasse",
        help_text="Gibt an, ob das Ticket an der Abendkasse verkauft wurde.",
    )
    late_collection = models.BooleanField(
        default=False,
        verbose_name="Späte Abholung (nach Deadline)",
        help_text="Markiert Bestellungen, bei denen der Kunde nach der Abholdeadline eintrifft. Diese Plätze werden nicht freigegeben.",
    )
    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Bestellung"
        verbose_name_plural = "Bestellungen"

    def __str__(self):
        return f"{self.customer_firstname} {self.customer_lastname} – {self.concert.name} ({self.confirmation_code})"

    @property
    def customer_full_name(self):
        return f"{self.customer_firstname} {self.customer_lastname}"

    @property
    def amount_adjusted(self):
        if not self.collected:
            return False
        return (
            self.collected_adult_count != self.adult_count
            or self.collected_child_count != self.child_count
        )

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
        # Only auto-recalculate total_price when not explicitly managing it
        # via update_fields (e.g. einlass_mark_collected sets its own price).
        update_fields = kwargs.get("update_fields")
        if not update_fields or "total_price" not in update_fields:
            self.total_price = (
                self.adult_count * self.concert.adult_price
                + self.child_count * self.concert.child_price
            )
        super().save(*args, **kwargs)
