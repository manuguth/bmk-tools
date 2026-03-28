import uuid

from django.db import models
from django.utils.text import slugify


class BringList(models.Model):
    EDIT_MODE_CHOICES = [
        ("free", "Jeder kann jeden Eintrag bearbeiten"),
        ("own", "Nur eigene Einträge bearbeiten (Session)"),
        ("insert_only", "Nur hinzufügen, kein Bearbeiten"),
    ]

    name = models.CharField(max_length=255, verbose_name="Name")
    description = models.TextField(blank=True, verbose_name="Beschreibung")
    date = models.DateField(null=True, blank=True, verbose_name="Datum")
    slug = models.SlugField(unique=True)
    public_token = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True,
    )
    edit_mode = models.CharField(
        max_length=20,
        choices=EDIT_MODE_CHOICES,
        default="own",
        verbose_name="Bearbeitungsmodus",
    )
    show_quantity = models.BooleanField(
        default=True,
        verbose_name="Mengenfeld anzeigen",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Bring-Liste"
        verbose_name_plural = "Bring-Listen"

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name)
            slug = base_slug
            counter = 1
            while BringList.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)


class BringItem(models.Model):
    bring_list = models.ForeignKey(
        BringList,
        on_delete=models.CASCADE,
        related_name="items",
    )
    label = models.CharField(max_length=255, verbose_name="Was wird mitgebracht")
    quantity = models.PositiveSmallIntegerField(default=1, verbose_name="Menge")
    contributor_name = models.CharField(max_length=255, verbose_name="Name")
    note = models.TextField(blank=True, verbose_name="Anmerkung")
    edit_token = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        verbose_name = "Eintrag"
        verbose_name_plural = "Einträge"

    def __str__(self):
        return f"{self.label} ({self.contributor_name})"
