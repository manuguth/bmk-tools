from django.contrib import admin
from django.http import HttpResponseRedirect
from django.urls import reverse

from info_mail.models import NewsletterSettings, WeeklyMails


class NewsletterSettingsAdmin(admin.ModelAdmin):
    fieldsets = [
        ("Versand", {"fields": ("recipient", "from_email", "default_test_email")}),
        ("Konzertmeister", {"fields": ("km_appointments_url", "km_requests_url", "excluded_appointment_names")}),
        ("MMV Newsletter", {"fields": ("mmv_newsletter_url", "mmv_newsletter_month")}),
    ]

    def has_add_permission(self, request):
        return not NewsletterSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        obj = NewsletterSettings.get_settings()
        return HttpResponseRedirect(
            reverse("admin:info_mail_newslettersettings_change", args=[obj.pk])
        )


class WeeklyMailsAdmin(admin.ModelAdmin):
    list_display = ["year", "week", "status", "reference", "upload_date"]
    list_filter = ["status", "year"]
    readonly_fields = ["reference", "html_file"]


admin.site.register(NewsletterSettings, NewsletterSettingsAdmin)
admin.site.register(WeeklyMails, WeeklyMailsAdmin)