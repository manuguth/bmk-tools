from django.contrib import admin


from info_mail.models import WeeklyMails


class WeeklyMailsAdmin(admin.ModelAdmin):
    pass


admin.site.register(WeeklyMails, WeeklyMailsAdmin)