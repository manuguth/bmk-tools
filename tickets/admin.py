from django import forms
from django.contrib import admin

from .models import Concert, TicketOrder


class ColorInput(forms.TextInput):
    """Renders as <input type="color"> for the Django admin color picker."""
    input_type = 'color'


class TicketOrderInline(admin.TabularInline):
    model = TicketOrder
    extra = 0
    readonly_fields = ("confirmation_code", "total_price", "created_at")
    fields = (
        "customer_firstname",
        "customer_lastname",
        "customer_email",
        "adult_count",
        "child_count",
        "total_price",
        "status",
        "confirmation_code",
        "created_at",
    )
    can_delete = True
    show_change_link = True


@admin.register(Concert)
class ConcertAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "date",
        "venue",
        "is_active",
        "adults_sold_display",
        "adults_remaining_display",
        "children_sold_display",
        "children_remaining_display",
        "created_at",
    )
    list_filter = ("is_active", "date")
    search_fields = ("name", "venue", "description")
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = ("created_at", "updated_at")
    inlines = [TicketOrderInline]
    fieldsets = (
        (
            "Konzertdaten",
            {
                "fields": ("name", "slug", "description", "date", "einlass", "venue", "image"),
            },
        ),
        (
            "Farben",
            {
                "fields": ("color_primary", "color_accent", "color_background"),
                "description": "Farbgebung der Konzertseite. Standardwerte: Navy #0d1b2a · Gold #c9a84c · Beige #f5f0e8",
            },
        ),
        (
            "Preise & Kapazität",
            {
                "fields": (
                    "adult_price",
                    "child_price",
                    "max_adults",
                    "max_children",
                    "abendkasse_extra_adults",
                    "abendkasse_extra_children",
                    "is_active",
                ),
            },
        ),
        (
            "Zeitstempel",
            {
                "fields": ("created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )

    def adults_sold_display(self, obj):
        return f"{obj.adults_sold}/{obj.max_adults}"

    adults_sold_display.short_description = "Erw. verkauft"

    def adults_remaining_display(self, obj):
        return obj.adults_remaining

    adults_remaining_display.short_description = "Erw. frei"

    def children_sold_display(self, obj):
        return f"{obj.children_sold}/{obj.max_children}"

    children_sold_display.short_description = "Kinder verk."

    def children_remaining_display(self, obj):
        return obj.children_remaining

    children_remaining_display.short_description = "Kinder frei"

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        if db_field.name in ('color_primary', 'color_accent', 'color_background'):
            kwargs['widget'] = ColorInput(attrs={'style': 'width:80px; height:40px; padding:2px; border-radius:4px;'})
        return super().formfield_for_dbfield(db_field, request, **kwargs)


@admin.register(TicketOrder)
class TicketOrderAdmin(admin.ModelAdmin):
    list_display = (
        "customer_full_name",
        "concert",
        "adult_count",
        "child_count",
        "total_price",
        "status",
        "created_at",
        "confirmation_code",
    )
    list_filter = ("status", "concert", "created_at")
    search_fields = (
        "customer_firstname",
        "customer_lastname",
        "customer_email",
        "confirmation_code",
        "concert__name",
    )
    readonly_fields = ("confirmation_code", "total_price", "created_at", "collected", "collected_adult_count", "collected_child_count")
    list_editable = ("status",)
    fieldsets = (
        (
            "Kundendaten",
            {
                "fields": ("customer_firstname", "customer_lastname", "customer_email", "customer_phone"),
            },
        ),
        (
            "Bestellung",
            {
                "fields": (
                    "concert",
                    "adult_count",
                    "child_count",
                    "total_price",
                    "notes",
                ),
            },
        ),
        (
            "Status & Code",
            {
                "fields": (
                    "status",
                    "confirmation_code",
                    "created_at",
                    "collected",
                    "collected_adult_count",
                    "collected_child_count",
                ),
            },
        ),
    )
