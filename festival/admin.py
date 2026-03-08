from django.contrib import admin
from .models import Festival, Shift, Task, Participant, TaskTemplate


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
    list_display = ("name", "shift", "required_helpers", "current_helpers_display", "km_event_display")
    list_filter = ("shift__festival", "shift__date", "konzertmeister_event_id")
    search_fields = ("name", "shift__name", "konzertmeister_event_id")
    readonly_fields = ("created_at", "updated_at")
    fieldsets = (
        ("Basic Information", {
            'fields': ('shift', 'name', 'description', 'required_helpers', 'special_requirements')
        }),
        ("Konzertmeister Integration", {
            'fields': ('konzertmeister_event_id',),
            'classes': ('collapse',),
            'description': 'Link this task to a Konzertmeister event for automatic participant sync'
        }),
        ("Timestamps", {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    def current_helpers_display(self, obj):
        return f"{obj.current_helpers}/{obj.required_helpers}"

    current_helpers_display.short_description = "Helpers (current/required)"

    def km_event_display(self, obj):
        return str(obj.konzertmeister_event_id) if obj.konzertmeister_event_id else "-"

    km_event_display.short_description = "KM Event ID"


@admin.register(Participant)
class ParticipantAdmin(admin.ModelAdmin):
    list_display = ("name", "task", "signed_up_at", "attended", "km_response_display")
    list_filter = ("attended", "task__shift__festival", "task__shift__date", "signed_up_at", "konzertmeister_response_status")
    search_fields = ("name", "task__name", "task__shift__name")
    readonly_fields = ("signed_up_at", "konzertmeister_user_id", "konzertmeister_response_status")
    fieldsets = (
        ("Basic Information", {
            'fields': ('task', 'name', 'notes', 'attended', 'signed_up_at')
        }),
        ("Konzertmeister Data", {
            'fields': ('konzertmeister_user_id', 'konzertmeister_response_status'),
            'classes': ('collapse',),
            'description': 'Read-only data from Konzertmeister sync'
        }),
    )
    actions = ["mark_attended", "mark_not_attended"]

    def km_response_display(self, obj):
        if obj.konzertmeister_response_status == 'positive':
            return "Positive"
        elif obj.konzertmeister_response_status == 'maybe':
            return "Maybe"
        return "-"

    km_response_display.short_description = "KM Response"

    def mark_attended(self, request, queryset):
        updated = queryset.update(attended=True)
        self.message_user(request, f"{updated} participants marked as attended.")

    mark_attended.short_description = "Mark selected as attended"

    def mark_not_attended(self, request, queryset):
        updated = queryset.update(attended=False)
        self.message_user(request, f"{updated} participants marked as not attended.")

    mark_not_attended.short_description = "Mark selected as not attended"


@admin.register(TaskTemplate)
class TaskTemplateAdmin(admin.ModelAdmin):
    list_display = ("name", "required_helpers", "created_at", "updated_at")
    search_fields = ("name", "description")
    readonly_fields = ("created_at", "updated_at")
