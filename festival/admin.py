from django.contrib import admin
from .models import Festival, Shift, Task, Participant


class ShiftInline(admin.TabularInline):
    model = Shift
    extra = 1


class TaskInline(admin.TabularInline):
    model = Task
    extra = 1


@admin.register(Festival)
class FestivalAdmin(admin.ModelAdmin):
    list_display = ("name", "start_date", "end_date", "status", "created_at")
    list_filter = ("status", "start_date", "end_date")
    search_fields = ("name", "description")
    prepopulated_fields = {"slug": ("name",)}
    inlines = [ShiftInline]


@admin.register(Shift)
class ShiftAdmin(admin.ModelAdmin):
    list_display = ("name", "date", "start_time", "end_time", "festival")
    list_filter = ("festival", "date")
    search_fields = ("name", "festival__name")
    inlines = [TaskInline]


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ("name", "shift", "required_helpers", "current_helpers_display")
    list_filter = ("shift__festival", "shift__date")
    search_fields = ("name", "shift__name")
    readonly_fields = ("created_at", "updated_at")

    def current_helpers_display(self, obj):
        return f"{obj.current_helpers}/{obj.required_helpers}"

    current_helpers_display.short_description = "Helpers (current/required)"


@admin.register(Participant)
class ParticipantAdmin(admin.ModelAdmin):
    list_display = ("name", "task", "signed_up_at", "attended")
    list_filter = ("attended", "task__shift__festival", "task__shift__date", "signed_up_at")
    search_fields = ("name", "task__name", "task__shift__name")
    readonly_fields = ("signed_up_at",)
    actions = ["mark_attended", "mark_not_attended"]

    def mark_attended(self, request, queryset):
        updated = queryset.update(attended=True)
        self.message_user(request, f"{updated} participants marked as attended.")

    mark_attended.short_description = "Mark selected as attended"

    def mark_not_attended(self, request, queryset):
        updated = queryset.update(attended=False)
        self.message_user(request, f"{updated} participants marked as not attended.")

    mark_not_attended.short_description = "Mark selected as not attended"
