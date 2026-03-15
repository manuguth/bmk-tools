from django.contrib import admin
from .models import OrderTemplate, OrderMenuItem, Order, OrderLineItem


class OrderMenuItemInline(admin.TabularInline):
    """Inline editor for menu items."""
    model = OrderMenuItem
    extra = 1
    fields = ('name', 'category', 'price', 'position')
    ordering = ('category', 'position')


class OrderLineItemInline(admin.TabularInline):
    """Inline editor for order line items."""
    model = OrderLineItem
    extra = 0
    readonly_fields = ('menu_item', 'unit_price', 'subtotal')
    fields = ('menu_item', 'quantity', 'unit_price', 'subtotal')
    can_delete = False

    def subtotal(self, obj):
        return f"€{obj.subtotal:.2f}"
    subtotal.short_description = "Subtotal"


@admin.register(OrderTemplate)
class OrderTemplateAdmin(admin.ModelAdmin):
    """Admin interface for order templates."""
    list_display = ('year', 'is_active', 'menu_item_count', 'order_count')
    list_filter = ('is_active', 'year', 'created_at')
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        ('Template Info', {
            'fields': ('year', 'is_active'),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )
    inlines = [OrderMenuItemInline]

    def menu_item_count(self, obj):
        return obj.menu_items.count()
    menu_item_count.short_description = 'Menu Items'

    def order_count(self, obj):
        return obj.orders.count()
    order_count.short_description = 'Orders'


@admin.register(OrderMenuItem)
class OrderMenuItemAdmin(admin.ModelAdmin):
    """Admin interface for menu items."""
    list_display = ('name', 'template', 'category', 'price', 'position')
    list_filter = ('template', 'category', 'created_at')
    search_fields = ('name',)
    readonly_fields = ('created_at', 'updated_at')
    ordering = ('template', 'category', 'position')
    fieldsets = (
        ('Item Info', {
            'fields': ('template', 'name', 'category', 'price', 'position'),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    """Admin interface for orders."""
    list_display = ('company_name', 'template', 'contact_name', 'status', 'total_price', 'created_at')
    list_filter = ('template__year', 'status', 'payment_method', 'created_at')
    search_fields = ('company_name', 'contact_name', 'contact_email')
    readonly_fields = ('created_at', 'updated_at', 'total_price_display')
    date_hierarchy = 'created_at'
    fieldsets = (
        ('Order Info', {
            'fields': ('template', 'company_name', 'status'),
        }),
        ('Contact Information', {
            'fields': ('contact_name', 'contact_email', 'contact_phone'),
        }),
        ('Order Details', {
            'fields': ('arrival_time', 'notes', 'total_price_display'),
        }),
        ('Payment', {
            'fields': ('payment_method', 'invoice_address'),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )
    inlines = [OrderLineItemInline]

    def total_price_display(self, obj):
        return f"€{obj.total_price:.2f}"
    total_price_display.short_description = 'Total Price'


@admin.register(OrderLineItem)
class OrderLineItemAdmin(admin.ModelAdmin):
    """Admin interface for order line items."""
    list_display = ('order', 'menu_item', 'quantity', 'unit_price', 'subtotal')
    list_filter = ('order__template', 'menu_item__category', 'order__created_at')
    search_fields = ('order__company_name', 'menu_item__name')
    readonly_fields = ('subtotal_display',)
    fieldsets = (
        ('Item Info', {
            'fields': ('order', 'menu_item', 'quantity', 'unit_price'),
        }),
        ('Subtotal', {
            'fields': ('subtotal_display',),
        }),
    )

    def subtotal_display(self, obj):
        return f"€{obj.subtotal:.2f}"
    subtotal_display.short_description = 'Subtotal'

    def has_add_permission(self, request):
        return False
