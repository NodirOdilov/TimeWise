"""
Invoice models: Invoice, InvoiceItem, Payment, PaymentMethod, TaxRate.
"""

import uuid
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models import Sum
from django.utils import timezone


class TaxRate(models.Model):
    """
    Tax rates that can be applied to invoices and line items.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "accounts.Organization",
        on_delete=models.CASCADE,
        related_name="tax_rates",
    )
    name = models.CharField(max_length=100, help_text="e.g., 'VAT', 'GST', 'Sales Tax'")
    rate = models.DecimalField(
        max_digits=5, decimal_places=2,
        help_text="Tax rate as a percentage (e.g., 20.00 for 20%)",
    )
    description = models.CharField(max_length=255, blank=True, default="")
    is_compound = models.BooleanField(
        default=False,
        help_text="If true, tax is calculated on subtotal + other taxes",
    )
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        unique_together = ["organization", "name"]

    def __str__(self):
        return f"{self.name} ({self.rate}%)"


class PaymentMethod(models.Model):
    """
    Payment methods accepted by the organization.
    """

    class MethodType(models.TextChoices):
        BANK_TRANSFER = "bank_transfer", "Bank Transfer"
        CREDIT_CARD = "credit_card", "Credit Card"
        PAYPAL = "paypal", "PayPal"
        STRIPE = "stripe", "Stripe"
        CHECK = "check", "Check"
        CASH = "cash", "Cash"
        OTHER = "other", "Other"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "accounts.Organization",
        on_delete=models.CASCADE,
        related_name="payment_methods",
    )
    name = models.CharField(max_length=100)
    method_type = models.CharField(
        max_length=20, choices=MethodType.choices, default=MethodType.BANK_TRANSFER
    )
    details = models.TextField(
        blank=True, default="",
        help_text="Payment instructions or account details shown on invoices",
    )
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.method_type})"


class Invoice(models.Model):
    """
    Invoice for billing clients for time entries and expenses.
    """

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SENT = "sent", "Sent"
        VIEWED = "viewed", "Viewed"
        PARTIALLY_PAID = "partially_paid", "Partially Paid"
        PAID = "paid", "Paid"
        OVERDUE = "overdue", "Overdue"
        VOID = "void", "Void"
        WRITTEN_OFF = "written_off", "Written Off"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "accounts.Organization",
        on_delete=models.CASCADE,
        related_name="invoices",
    )
    client = models.ForeignKey(
        "projects.Client",
        on_delete=models.PROTECT,
        related_name="invoices",
    )
    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="invoices",
    )
    invoice_number = models.CharField(max_length=50, unique=True)
    reference = models.CharField(
        max_length=100, blank=True, default="",
        help_text="Client PO number or reference",
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.DRAFT
    )
    issue_date = models.DateField(default=timezone.now)
    due_date = models.DateField()
    currency = models.CharField(
        max_length=3,
        choices=settings.SUPPORTED_CURRENCIES,
        default=settings.DEFAULT_CURRENCY,
    )
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    discount_percent = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        help_text="Discount as a percentage",
    )
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    amount_paid = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    amount_due = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    tax_rate = models.ForeignKey(
        TaxRate,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="invoices",
    )
    payment_method = models.ForeignKey(
        PaymentMethod,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="invoices",
    )
    notes = models.TextField(blank=True, default="", help_text="Notes shown on invoice")
    internal_notes = models.TextField(
        blank=True, default="", help_text="Internal notes not shown to client"
    )
    terms = models.TextField(
        blank=True, default="",
        help_text="Payment terms and conditions",
    )
    footer = models.TextField(
        blank=True, default="",
        help_text="Footer text shown at the bottom of the invoice",
    )
    sent_at = models.DateTimeField(null=True, blank=True)
    viewed_at = models.DateTimeField(null=True, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_invoices",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-issue_date", "-invoice_number"]
        indexes = [
            models.Index(fields=["organization", "status"]),
            models.Index(fields=["client"]),
            models.Index(fields=["due_date"]),
        ]

    def __str__(self):
        return f"{self.invoice_number} - {self.client.name}"

    def save(self, *args, **kwargs):
        self.calculate_totals()
        super().save(*args, **kwargs)

    def calculate_totals(self):
        """Recalculate invoice totals from line items."""
        self.subtotal = (
            self.items.aggregate(total=Sum("total"))["total"]
            or Decimal("0.00")
        )

        if self.discount_percent > 0:
            self.discount_amount = (
                self.subtotal * self.discount_percent / Decimal("100")
            ).quantize(Decimal("0.01"))

        after_discount = self.subtotal - self.discount_amount

        if self.tax_rate:
            self.tax_amount = (
                after_discount * self.tax_rate.rate / Decimal("100")
            ).quantize(Decimal("0.01"))
        else:
            self.tax_amount = Decimal("0.00")

        self.total_amount = after_discount + self.tax_amount
        self.amount_due = self.total_amount - self.amount_paid

    @property
    def is_overdue(self):
        return (
            self.status in [self.Status.SENT, self.Status.VIEWED]
            and self.due_date < timezone.now().date()
        )

    @property
    def days_until_due(self):
        delta = self.due_date - timezone.now().date()
        return delta.days


class InvoiceItem(models.Model):
    """
    Line items on an invoice.
    """

    class ItemType(models.TextChoices):
        TIME = "time", "Time Entry"
        EXPENSE = "expense", "Expense"
        FIXED = "fixed", "Fixed Amount"
        DISCOUNT = "discount", "Discount"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    invoice = models.ForeignKey(
        Invoice, on_delete=models.CASCADE, related_name="items"
    )
    item_type = models.CharField(
        max_length=10, choices=ItemType.choices, default=ItemType.TIME
    )
    description = models.TextField()
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    total = models.DecimalField(max_digits=12, decimal_places=2)
    time_entry = models.ForeignKey(
        "time_entries.TimeEntry",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="invoice_items",
    )
    expense = models.ForeignKey(
        "expenses.Expense",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="invoice_items",
    )
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["sort_order", "created_at"]

    def __str__(self):
        return f"{self.description[:50]} - {self.total}"

    def save(self, *args, **kwargs):
        self.total = (self.quantity * self.unit_price).quantize(Decimal("0.01"))
        super().save(*args, **kwargs)


class Payment(models.Model):
    """
    Payment records for invoices.
    """

    class PaymentStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"
        REFUNDED = "refunded", "Refunded"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    invoice = models.ForeignKey(
        Invoice, on_delete=models.CASCADE, related_name="payments"
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(
        max_length=3,
        choices=settings.SUPPORTED_CURRENCIES,
        default=settings.DEFAULT_CURRENCY,
    )
    payment_method = models.ForeignKey(
        PaymentMethod,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    status = models.CharField(
        max_length=20,
        choices=PaymentStatus.choices,
        default=PaymentStatus.COMPLETED,
    )
    payment_date = models.DateField(default=timezone.now)
    reference = models.CharField(
        max_length=255, blank=True, default="",
        help_text="Transaction reference or check number",
    )
    notes = models.TextField(blank=True, default="")
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="recorded_payments",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-payment_date"]

    def __str__(self):
        return f"Payment {self.amount} for {self.invoice.invoice_number}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.update_invoice_paid_amount()

    def update_invoice_paid_amount(self):
        """Update the invoice's paid amount after recording a payment."""
        invoice = self.invoice
        total_paid = invoice.payments.filter(
            status=self.PaymentStatus.COMPLETED
        ).aggregate(total=Sum("amount"))["total"] or Decimal("0.00")

        invoice.amount_paid = total_paid
        invoice.amount_due = invoice.total_amount - total_paid

        if total_paid >= invoice.total_amount:
            invoice.status = Invoice.Status.PAID
            invoice.paid_at = timezone.now()
        elif total_paid > 0:
            invoice.status = Invoice.Status.PARTIALLY_PAID

        invoice.save(update_fields=[
            "amount_paid", "amount_due", "status", "paid_at", "updated_at",
        ])
