from django import forms
from django.utils import timezone

from .models import Concert, TicketOrder


class TicketOrderForm(forms.ModelForm):
    class Meta:
        model = TicketOrder
        fields = [
            "customer_name",
            "customer_email",
            "customer_phone",
            "adult_count",
            "child_count",
            "notes",
        ]
        widgets = {
            "customer_name": forms.TextInput(
                attrs={
                    "class": "form-control form-control-lg",
                    "placeholder": "Ihr vollständiger Name",
                }
            ),
            "customer_email": forms.EmailInput(
                attrs={
                    "class": "form-control form-control-lg",
                    "placeholder": "ihre@email.de",
                }
            ),
            "customer_phone": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Optional: +49 123 456789",
                }
            ),
            "adult_count": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "min": "0",
                    "max": "20",
                    "id": "id_adult_count",
                }
            ),
            "child_count": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "min": "0",
                    "max": "20",
                    "id": "id_child_count",
                }
            ),
            "notes": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "placeholder": "Optionale Anmerkungen zu Ihrer Bestellung",
                }
            ),
        }
        labels = {
            "customer_name": "Name",
            "customer_email": "E-Mail-Adresse",
            "customer_phone": "Telefon (optional)",
            "adult_count": "Erwachsene",
            "child_count": "Kinder",
            "notes": "Anmerkungen (optional)",
        }

    def clean(self):
        cleaned_data = super().clean()
        adult_count = cleaned_data.get("adult_count") or 0
        child_count = cleaned_data.get("child_count") or 0
        if adult_count + child_count < 1:
            raise forms.ValidationError(
                "Bitte wählen Sie mindestens ein Ticket (Erwachsene oder Kinder)."
            )
        return cleaned_data


class ConcertForm(forms.ModelForm):
    date = forms.DateTimeField(
        input_formats=["%Y-%m-%dT%H:%M"],
        widget=forms.DateTimeInput(
            attrs={"class": "form-control", "type": "datetime-local"},
            format="%Y-%m-%dT%H:%M",
        ),
        label="Datum & Uhrzeit",
    )

    class Meta:
        model = Concert
        fields = [
            "name",
            "slug",
            "description",
            "date",
            "venue",
            "adult_price",
            "child_price",
            "max_adults",
            "max_children",
            "is_active",
            "image",
            "color_primary",
            "color_accent",
            "color_background",
        ]
        widgets = {
            "name": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "z.B. Sommerkonzert 2026",
                }
            ),
            "slug": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "z.B. sommerkonzert-2026",
                    "id": "id_slug",
                }
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 4,
                    "placeholder": "Beschreibung des Konzerts",
                }
            ),
            "venue": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "z.B. Mehrzweckhalle Buggingen",
                }
            ),
            "adult_price": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "min": "0",
                    "step": "0.50",
                    "placeholder": "12.00",
                }
            ),
            "child_price": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "min": "0",
                    "step": "0.50",
                    "placeholder": "6.00",
                }
            ),
            "max_adults": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "min": "1",
                    "placeholder": "150",
                }
            ),
            "max_children": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "min": "0",
                    "placeholder": "50",
                }
            ),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "image": forms.ClearableFileInput(attrs={"class": "form-control"}),
            "color_primary": forms.TextInput(
                attrs={"type": "color", "class": "form-control form-control-color"}
            ),
            "color_accent": forms.TextInput(
                attrs={"type": "color", "class": "form-control form-control-color"}
            ),
            "color_background": forms.TextInput(
                attrs={"type": "color", "class": "form-control form-control-color"}
            ),
        }
        labels = {
            "name": "Bezeichnung",
            "slug": "URL-Slug",
            "description": "Beschreibung",
            "venue": "Veranstaltungsort",
            "adult_price": "Preis Erwachsene (€)",
            "child_price": "Preis Kinder bis 12 Jahre (€)",
            "max_adults": "Max. Erwachsenen-Tickets",
            "max_children": "Max. Kinder-Tickets (bis 12 Jahre)",
            "is_active": "Vorverkauf aktiv",
            "image": "Konzertplakat (optional)",
            "color_primary": "Primärfarbe",
            "color_accent": "Akzentfarbe",
            "color_background": "Hintergrundfarbe",
        }
        help_texts = {
            "color_primary": "Standard: #0d1b2a (Navy)",
            "color_accent": "Standard: #c9a84c (Gold)",
            "color_background": "Standard: #f5f0e8 (Beige)",
        }

    def clean_date(self):
        date = self.cleaned_data.get("date")
        if date and timezone.is_naive(date):
            date = timezone.make_aware(date)
        return date
