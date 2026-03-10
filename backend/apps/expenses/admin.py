"""
Admin configuration for the expenses app.
"""

from django.contrib import admin

from .models import Expense, ExpenseCategory, Receipt


class ReceiptInline(admin.TabularInline):
    model = Receipt
    extra = 0
    readonly_fields = ["uploaded_at"]


@admin.register(ExpenseCategory)
class ExpenseCategoryAdmin(admin.ModelAdmin):
    list_display = [
        "name", "organization", "color",
        "is_billable_default", "is_active",
    ]
    list_filter = ["is_active", "is_billable_default"]
    search_fields = ["name"]


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = [
        "description", "user", "project", "category",
        "amount", "currency", "date", "status",
        "is_billable", "is_reimbursable",
    ]
    list_filter = [
        "status", "is_billable", "is_reimbursable",
        "currency", "category", "organization",
    ]
    search_fields = ["description", "merchant", "user__email"]
    raw_id_fields = ["user", "project", "invoice", "approved_by"]
    readonly_fields = ["approved_at", "created_at", "updated_at"]
    date_hierarchy = "date"
    inlines = [ReceiptInline]


@admin.register(Receipt)
class ReceiptAdmin(admin.ModelAdmin):
    list_display = [
        "filename", "expense", "file_size",
        "content_type", "uploaded_by", "uploaded_at",
    ]
    raw_id_fields = ["expense", "uploaded_by"]
