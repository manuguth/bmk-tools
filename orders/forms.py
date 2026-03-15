from django import forms
from django.forms import inlineformset_factory
from .models import Order, OrderTemplate, OrderMenuItem, OrderLineItem


class OrderTemplateForm(forms.ModelForm):
    """Admin form for creating/editing order templates."""

    class Meta:
        model = OrderTemplate
        fields = ['year', 'is_active']
        widgets = {
            'year': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'z.B. 2026',
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
            }),
        }


class OrderMenuItemForm(forms.ModelForm):
    """Admin form for managing menu items."""

    class Meta:
        model = OrderMenuItem
        fields = ['name', 'category', 'price', 'position']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'z.B. Grillwurst mit Pommes Frites',
            }),
            'category': forms.Select(attrs={
                'class': 'form-select',
            }),
            'price': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0',
                'placeholder': '0.00',
            }),
            'position': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0',
                'placeholder': '0',
            }),
        }


# Formset for managing multiple menu items at once
OrderMenuItemFormSet = inlineformset_factory(
    OrderTemplate,
    OrderMenuItem,
    form=OrderMenuItemForm,
    extra=1,
    can_delete=True,
)


class OrderForm(forms.ModelForm):
    """Public form for submitting orders."""

    class Meta:
        model = Order
        fields = [
            'company_name',
            'contact_name',
            'contact_email',
            'contact_phone',
            'arrival_time',
            'payment_method',
            'invoice_address',
            'notes',
        ]
        widgets = {
            'company_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Name des Betriebs',
                'required': True,
            }),
            'contact_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Name der Kontaktperson',
                'required': True,
            }),
            'contact_email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'E-Mail Adresse',
                'required': True,
            }),
            'contact_phone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Telefon (optional)',
            }),
            'arrival_time': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ankunftszeit (z.B. 12:30)',
                'type': 'time',
            }),
            'payment_method': forms.RadioSelect(attrs={
                'class': 'form-check-input',
            }),
            'invoice_address': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Rechnungsadresse (Name, Straße, Hausnummer, PLZ, Ort)',
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Besondere Wünsche oder Anmerkungen (optional)',
            }),
        }

    def __init__(self, *args, template=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.template = template
        # Set help texts for fields
        self.fields['company_name'].label = 'Name des Betriebs'
        self.fields['contact_name'].label = 'Ansprechperson'
        self.fields['contact_email'].label = 'E-Mail'
        self.fields['contact_phone'].label = 'Telefon'
        self.fields['arrival_time'].label = 'Erwartete Ankunftszeit'
        self.fields['payment_method'].label = 'Zahlungsweise'
        self.fields['invoice_address'].label = 'Rechnungsadresse'
        self.fields['notes'].label = 'Anmerkungen'

    def clean(self):
        cleaned_data = super().clean()
        payment_method = cleaned_data.get('payment_method')
        invoice_address = cleaned_data.get('invoice_address')

        # If invoice payment method, require invoice address
        if payment_method == 'invoice' and not invoice_address:
            self.add_error(
                'invoice_address',
                'Rechnungsadresse erforderlich für Rechnungszahlung'
            )

        # Check for duplicate company name if template is set
        if self.template:
            company_name = cleaned_data.get('company_name')
            if company_name and Order.objects.filter(
                template=self.template,
                company_name__iexact=company_name
            ).exists():
                self.add_error(
                    'company_name',
                    f'Es existiert bereits eine Bestellung von "{company_name}" für dieses Jahr.'
                )

        return cleaned_data


class OrderLineItemForm(forms.Form):
    """Dynamic form for ordering menu items in the public form."""

    quantity = forms.IntegerField(
        min_value=0,
        initial=0,
        required=False,
        widget=forms.NumberInput(attrs={
            'class': 'form-control form-control-sm',
            'style': 'width: 80px;',
            'min': '0',
        })
    )

    def __init__(self, menu_item, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.menu_item = menu_item

    @property
    def item_name(self):
        return self.menu_item.name

    @property
    def item_price(self):
        return self.menu_item.price

    @property
    def item_category(self):
        return self.menu_item.get_category_display()
