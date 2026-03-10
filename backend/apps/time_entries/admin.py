"""
Admin configuration for the time_entries app.
"""

from django.contrib import admin

from .models import TimeEntry, Timer, TimeApproval


@admin.register(TimeEntry)
class TimeEntryAdmin(admin.ModelAdmin):
    list_display = [
        "user", "project", "date", "duration_minutes", "formatted_duration",
        "is_billable", "hourly_rate", "billable_amount", "status",
        "entry_type", "is_running",
    ]
    list_filter = [
        "status", "entry_type", "is_billable", "is_running",
        "date", "organization",
    ]
    search_fields = ["description", "user__email", "project__name"]
    raw_id_fields = ["user", "project", "task", "invoice"]
    readonly_fields = [
        "billable_amount", "cost_amount", "created_at", "updated_at",
    ]
    date_hierarchy = "date"


@admin.register(Timer)
class TimerAdmin(admin.ModelAdmin):
    list_display = ["user", "project", "started_at", "elapsed_minutes"]
    raw_id_fields = ["user", "time_entry", "project", "task"]


@admin.register(TimeApproval)
class TimeApprovalAdmin(admin.ModelAdmin):
    list_display = ["time_entry", "reviewer", "action", "reviewed_at"]
    list_filter = ["action"]
    raw_id_fields = ["time_entry", "reviewer"]
