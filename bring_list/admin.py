from django.contrib import admin

from .models import BringItem, BringList


class BringItemInline(admin.TabularInline):
    model = BringItem
    extra = 0
    readonly_fields = ("edit_token", "created_at")
    fields = ("label", "quantity", "contributor_name", "note", "edit_token", "created_at")


@admin.register(BringList)
class BringListAdmin(admin.ModelAdmin):
    list_display = ("name", "date", "edit_mode", "created_at")
    list_filter = ("edit_mode",)
    search_fields = ("name",)
    readonly_fields = ("public_token", "slug", "created_at")
    inlines = [BringItemInline]


@admin.register(BringItem)
class BringItemAdmin(admin.ModelAdmin):
    list_display = ("label", "quantity", "contributor_name", "bring_list", "created_at")
    list_filter = ("bring_list",)
    search_fields = ("label", "contributor_name")
    readonly_fields = ("edit_token", "created_at")
