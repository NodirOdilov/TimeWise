"""
Admin configuration for the invoicing app.
"""

from django.contrib import admin

from .models import Invoice, InvoiceItem, Payment, PaymentMethod, TaxRate


class InvoiceItemInline(admin.TabularInline):
    model = InvoiceItem
    extra = 0
    readonly_fields = ["total"]


class PaymentInline(admin.TabularInline):
    model = Payment
    extra = 0
    readonly_fields = ["created_at"]


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = [
        "invoice_number", "client", "status", "issue_date",
        "due_date", "total_amount", "amount_paid", "amount_due",
        "currency",
    ]
    list_filter = ["status", "currency", "organization"]
    search_fields = ["invoice_number", "reference", "client__name"]
    raw_id_fields = ["client", "project", "created_by"]
    readonly_fields = [
        "subtotal", "tax_amount", "total_amount",
        "amount_paid", "amount_due", "created_at", "updated_at",
    ]
    date_hierarchy = "issue_date"
    inlines = [InvoiceItemInline, PaymentInline]
    fieldsets = (
        (None, {"fields": (
            "organization", "client", "project", "invoice_number",
            "reference", "status",
        )}),
        ("Dates", {"fields": (
            "issue_date", "due_date", "sent_at", "viewed_at", "paid_at",
        )}),
        ("Amounts", {"fields": (
            "currency", "subtotal", "discount_percent", "discount_amount",
            "tax_rate", "tax_amount", "total_amount", "amount_paid", "amount_due",
        )}),
        ("Payment", {"fields": ("payment_method",)}),
        ("Content", {"fields": ("notes", "internal_notes", "terms", "footer")}),
        ("Metadata", {"fields": ("created_by", "created_at", "updated_at")}),
    )


@admin.register(InvoiceItem)
class InvoiceItemAdmin(admin.ModelAdmin):
    list_display = [
        "invoice", "item_type", "description", "quantity",
        "unit_price", "total",
    ]
    list_filter = ["item_type"]
    raw_id_fields = ["invoice", "time_entry", "expense"]


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = [
        "invoice", "amount", "currency", "payment_method",
        "status", "payment_date", "recorded_by",
    ]
    list_filter = ["status", "currency"]
    raw_id_fields = ["invoice", "recorded_by"]
    date_hierarchy = "payment_date"


@admin.register(PaymentMethod)
class PaymentMethodAdmin(admin.ModelAdmin):
    list_display = ["name", "method_type", "organization", "is_default", "is_active"]
    list_filter = ["method_type", "is_active"]


@admin.register(TaxRate)
class TaxRateAdmin(admin.ModelAdmin):
    list_display = ["name", "rate", "organization", "is_default", "is_active"]
    list_filter = ["is_active"]
