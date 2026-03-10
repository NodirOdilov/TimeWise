"""
Admin configuration for the projects app.
"""

from django.contrib import admin

from .models import Client, Project, ProjectMember, ProjectBudget, Task


class ProjectMemberInline(admin.TabularInline):
    model = ProjectMember
    extra = 0
    raw_id_fields = ["user"]


class TaskInline(admin.TabularInline):
    model = Task
    extra = 0
    fields = ["name", "status", "priority", "assignee", "estimated_hours", "due_date"]


class ProjectBudgetInline(admin.TabularInline):
    model = ProjectBudget
    extra = 0


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = [
        "name", "organization", "contact_name", "contact_email",
        "currency", "payment_terms_days", "is_active", "created_at",
    ]
    list_filter = ["is_active", "currency", "organization"]
    search_fields = ["name", "contact_name", "contact_email"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = [
        "name", "code", "organization", "client", "status",
        "billing_type", "hourly_rate", "is_billable",
        "start_date", "end_date", "created_at",
    ]
    list_filter = ["status", "billing_type", "is_billable", "organization"]
    search_fields = ["name", "code", "description"]
    readonly_fields = ["created_at", "updated_at"]
    inlines = [ProjectMemberInline, TaskInline, ProjectBudgetInline]
    fieldsets = (
        (None, {"fields": (
            "organization", "client", "name", "code", "description", "color",
        )}),
        ("Status & Billing", {"fields": (
            "status", "billing_type", "hourly_rate", "fixed_price",
            "estimated_hours", "is_billable", "is_public",
        )}),
        ("Schedule", {"fields": ("start_date", "end_date")}),
        ("Metadata", {"fields": ("tags", "created_at", "updated_at")}),
    )


@admin.register(ProjectMember)
class ProjectMemberAdmin(admin.ModelAdmin):
    list_display = ["project", "user", "role", "hourly_rate", "is_active", "joined_at"]
    list_filter = ["role", "is_active"]
    search_fields = ["project__name", "user__email"]
    raw_id_fields = ["project", "user"]


@admin.register(ProjectBudget)
class ProjectBudgetAdmin(admin.ModelAdmin):
    list_display = [
        "project", "budget_type", "amount", "currency",
        "period_start", "period_end", "is_active",
    ]
    list_filter = ["budget_type", "is_active", "currency"]
    search_fields = ["project__name"]


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = [
        "name", "project", "status", "priority",
        "assignee", "estimated_hours", "due_date",
    ]
    list_filter = ["status", "priority", "is_billable"]
    search_fields = ["name", "description", "project__name"]
    raw_id_fields = ["project", "assignee"]
    readonly_fields = ["created_at", "updated_at"]
