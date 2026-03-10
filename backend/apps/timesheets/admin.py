"""
Admin configuration for the timesheets app.
"""

from django.contrib import admin

from .models import WeeklyTimesheet, TimesheetApproval


class TimesheetApprovalInline(admin.TabularInline):
    model = TimesheetApproval
    extra = 0
    readonly_fields = ["reviewed_at"]


@admin.register(WeeklyTimesheet)
class WeeklyTimesheetAdmin(admin.ModelAdmin):
    list_display = [
        "user", "week_start", "week_end", "status",
        "total_hours", "billable_hours", "overtime_hours",
        "submitted_at",
    ]
    list_filter = ["status", "organization"]
    search_fields = ["user__email", "user__first_name", "user__last_name"]
    raw_id_fields = ["user"]
    readonly_fields = ["created_at", "updated_at"]
    date_hierarchy = "week_start"
    inlines = [TimesheetApprovalInline]


@admin.register(TimesheetApproval)
class TimesheetApprovalAdmin(admin.ModelAdmin):
    list_display = ["timesheet", "reviewer", "action", "reviewed_at"]
    list_filter = ["action"]
    raw_id_fields = ["timesheet", "reviewer"]
