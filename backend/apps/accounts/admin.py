"""
Admin configuration for the accounts app.
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _

from .models import User, Organization, Team, BillingRate


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = [
        "email", "first_name", "last_name", "organization",
        "role", "is_billable", "is_active", "date_joined",
    ]
    list_filter = ["role", "is_active", "is_billable", "organization"]
    search_fields = ["email", "first_name", "last_name"]
    ordering = ["email"]
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        (_("Personal info"), {"fields": (
            "first_name", "last_name", "avatar", "phone", "job_title",
        )}),
        (_("Organization"), {"fields": (
            "organization", "role", "timezone",
        )}),
        (_("Billing"), {"fields": (
            "default_hourly_rate", "is_billable", "weekly_capacity_hours",
        )}),
        (_("Permissions"), {"fields": (
            "is_active", "is_staff", "is_superuser", "groups",
            "user_permissions",
        )}),
        (_("Important dates"), {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": (
                "email", "first_name", "last_name", "password1", "password2",
                "organization", "role",
            ),
        }),
    )


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = [
        "name", "slug", "default_currency", "is_active",
        "invoice_prefix", "created_at",
    ]
    list_filter = ["is_active", "default_currency"]
    search_fields = ["name", "slug"]
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ["name", "organization", "lead", "is_active", "created_at"]
    list_filter = ["is_active", "organization"]
    search_fields = ["name"]
    filter_horizontal = ["members"]


@admin.register(BillingRate)
class BillingRateAdmin(admin.ModelAdmin):
    list_display = [
        "organization", "user", "project", "rate_type",
        "rate", "currency", "effective_from", "effective_to", "is_active",
    ]
    list_filter = ["rate_type", "currency", "is_active"]
    search_fields = ["organization__name", "user__email", "project__name"]
