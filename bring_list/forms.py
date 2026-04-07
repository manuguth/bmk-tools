from django import forms
from django.core.exceptions import ValidationError
from django.utils.text import slugify

from .models import BringItem, BringList

_input_attrs = {
    "class": "form-control",
    "style": (
        "border: 2px solid #e5e7eb; border-radius: 8px; "
        "padding: 0.75rem 1rem; font-size: 0.95rem; transition: all 0.3s ease;"
    ),
    "onfocus": (
        "this.style.borderColor='var(--festival-primary)';"
        "this.style.boxShadow='0 0 0 3px rgba(99,102,241,0.1)';"
    ),
    "onblur": "this.style.borderColor='#e5e7eb';this.style.boxShadow='none';",
}


class BringItemForm(forms.ModelForm):
    class Meta:
        model = BringItem
        fields = ["label", "quantity", "contributor_name", "note"]
        labels = {
            "label": "Was bringst du mit?",
            "quantity": "Menge",
            "contributor_name": "Dein Name",
            "note": "Anmerkung (optional)",
        }
        widgets = {
            "label": forms.TextInput(
                attrs={**_input_attrs, "placeholder": "z. B. Hefezopf"}
            ),
            "quantity": forms.NumberInput(
                attrs={**_input_attrs, "min": 1, "placeholder": "1"}
            ),
            "contributor_name": forms.TextInput(
                attrs={**_input_attrs, "placeholder": "Dein Name"}
            ),
            "note": forms.Textarea(
                attrs={**_input_attrs, "rows": 2, "placeholder": "Optionale Anmerkung"}
            ),
        }

    def __init__(self, *args, show_quantity=True, **kwargs):
        super().__init__(*args, **kwargs)
        if not show_quantity:
            del self.fields["quantity"]


class BringListForm(forms.ModelForm):
    class Meta:
        model = BringList
        fields = ["name", "slug", "description", "date", "edit_mode", "show_quantity"]
        labels = {
            "name": "Name der Liste",
            "slug": "Eigene URL (Slug)",
            "description": "Beschreibung",
            "date": "Datum (optional)",
            "edit_mode": "Bearbeitungsmodus",
        }
        widgets = {
            "name": forms.TextInput(
                attrs={**_input_attrs, "placeholder": "z. B. Sommerfest 2026"}
            ),
            "slug": forms.TextInput(
                attrs={**_input_attrs, "placeholder": "z. B. sommerfest-2026"}
            ),
            "description": forms.Textarea(
                attrs={**_input_attrs, "rows": 3, "placeholder": "Kurze Beschreibung (optional)"}
            ),
            "date": forms.DateInput(
                attrs={**_input_attrs, "type": "date"}
            ),
            "edit_mode": forms.Select(
                attrs={
                    "class": "form-select",
                    "style": (
                        "border: 2px solid #e5e7eb; border-radius: 8px; "
                        "padding: 0.75rem 1rem; font-size: 0.95rem;"
                    ),
                }
            ),
        }

    def clean_slug(self):
        slug = self.cleaned_data.get("slug", "").strip()
        if not slug:
            return slug
        if slugify(slug) != slug:
            raise ValidationError(
                "Nur Kleinbuchstaben, Ziffern und Bindestriche erlaubt."
            )
        if slug == "admin":
            raise ValidationError(
                '"admin" ist reserviert und kann nicht als Slug verwendet werden.'
            )
        qs = BringList.objects.filter(slug=slug)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise ValidationError("Dieser Slug wird bereits verwendet.")
        return slug
