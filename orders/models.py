from django.db import models
from django.core.validators import MinValueValidator


class OrderTemplate(models.Model):
    """Container for a year's menu configuration."""

    year = models.IntegerField(unique=True, help_text="Year for this order template (e.g., 2026)")
    is_active = models.BooleanField(
        default=False,
        help_text="Only orders with active template can be submitted"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-year"]
        verbose_name = "Order Template"
        verbose_name_plural = "Order Templates"

    def __str__(self):
        return f"Menu {self.year} {'(Active)' if self.is_active else '(Inactive)'}"

    def save(self, *args, **kwargs):
        """Ensure only one active template exists at a time."""
        if self.is_active:
            OrderTemplate.objects.exclude(pk=self.pk).filter(is_active=True).update(is_active=False)
        super().save(*args, **kwargs)


class OrderMenuItem(models.Model):
    """Individual menu items (food/drinks)."""

    CATEGORY_CHOICES = [
        ('food', 'Speisen'),
        ('drink', 'Getränke'),
    ]

    template = models.ForeignKey(
        OrderTemplate,
        on_delete=models.CASCADE,
        related_name='menu_items'
    )
    name = models.CharField(
        max_length=255,
        help_text="e.g., 'Grillwurst mit Pommes Frites'"
    )
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES)
    price = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        help_text="Price in EUR"
    )
    position = models.IntegerField(
        default=0,
        help_text="Order in which items appear in the form"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['category', 'position']
        unique_together = ('template', 'name')
        verbose_name = "Order Menu Item"
        verbose_name_plural = "Order Menu Items"

    def __str__(self):
        return f"{self.name} (€{self.price})"


class Order(models.Model):
    """A submitted company order."""

    PAYMENT_CHOICES = [
        ('invoice', 'Rechnung an folgende Adresse'),
        ('pickup', 'Zahlung bei Abholung (bar oder EC-Karte)'),
    ]

    STATUS_CHOICES = [
        ('pending', 'Ausstehend'),
        ('confirmed', 'Bestätigt'),
    ]

    template = models.ForeignKey(
        OrderTemplate,
        on_delete=models.PROTECT,
        related_name='orders',
        help_text="Which year/menu this order is for"
    )
    company_name = models.CharField(
        max_length=255,
        help_text="Name of the company placing the order"
    )
    contact_name = models.CharField(
        max_length=255,
        help_text="Name of person making the order"
    )
    contact_email = models.EmailField()
    contact_phone = models.CharField(
        max_length=20,
        blank=True,
        help_text="Optional phone number"
    )
    arrival_time = models.CharField(
        max_length=5,
        blank=True,
        help_text="Expected arrival time (e.g., '12:30')"
    )
    payment_method = models.CharField(
        max_length=50,
        choices=PAYMENT_CHOICES
    )
    invoice_address = models.TextField(
        blank=True,
        help_text="Only required if payment_method is 'invoice'"
    )
    notes = models.TextField(
        blank=True,
        help_text="Additional notes or special requests"
    )
    status = models.CharField(
        max_length=50,
        choices=STATUS_CHOICES,
        default='pending'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        unique_together = ('template', 'company_name')
        verbose_name = "Order"
        verbose_name_plural = "Orders"
        constraints = [
            models.UniqueConstraint(
                fields=['template', 'company_name'],
                name='unique_order_per_company_per_year'
            )
        ]

    def __str__(self):
        return f"Order from {self.company_name} ({self.template.year})"

    @property
    def total_price(self):
        """Calculate total price of all line items."""
        return sum(item.subtotal for item in self.line_items.all())


class OrderLineItem(models.Model):
    """Items within an order."""

    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='line_items'
    )
    menu_item = models.ForeignKey(
        OrderMenuItem,
        on_delete=models.PROTECT,
        help_text="Reference to menu item (read-only for historical purposes)"
    )
    quantity = models.IntegerField(
        validators=[MinValueValidator(1)],
        help_text="Quantity ordered"
    )
    unit_price = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        help_text="Price at time of order (snapshot from menu)"
    )

    class Meta:
        ordering = ['menu_item__category', 'menu_item__position']
        verbose_name = "Order Line Item"
        verbose_name_plural = "Order Line Items"
        unique_together = ('order', 'menu_item')

    def __str__(self):
        return f"{self.quantity}x {self.menu_item.name}"

    @property
    def subtotal(self):
        """Calculate subtotal for this line item."""
        return self.unit_price * self.quantity
