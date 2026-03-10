"""
Expense models: Expense, ExpenseCategory, Receipt.
"""

import uuid
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone


class ExpenseCategory(models.Model):
    """
    Categories for organizing expenses.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "accounts.Organization",
        on_delete=models.CASCADE,
        related_name="expense_categories",
    )
    name = models.CharField(max_length=100)
    description = models.CharField(max_length=255, blank=True, default="")
    color = models.CharField(max_length=7, default="#6B7280")
    is_billable_default = models.BooleanField(
        default=True,
        help_text="Default billable status for expenses in this category",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "Expense categories"
        unique_together = ["organization", "name"]

    def __str__(self):
        return self.name


class Expense(models.Model):
    """
    An expense that can be billed to a client or tracked for internal records.
    """

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SUBMITTED = "submitted", "Submitted"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        INVOICED = "invoiced", "Invoiced"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "accounts.Organization",
        on_delete=models.CASCADE,
        related_name="expenses",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="expenses",
    )
    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="expenses",
    )
    category = models.ForeignKey(
        ExpenseCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="expenses",
    )
    description = models.TextField()
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(
        max_length=3,
        choices=settings.SUPPORTED_CURRENCIES,
        default=settings.DEFAULT_CURRENCY,
    )
    date = models.DateField(default=timezone.now)
    is_billable = models.BooleanField(default=True)
    is_reimbursable = models.BooleanField(
        default=False,
        help_text="Whether this expense should be reimbursed to the user",
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.DRAFT
    )
    merchant = models.CharField(max_length=255, blank=True, default="")
    reference_number = models.CharField(
        max_length=100, blank=True, default="",
        help_text="Receipt or transaction reference number",
    )
    invoice = models.ForeignKey(
        "invoicing.Invoice",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="expenses",
    )
    notes = models.TextField(blank=True, default="")
    tags = models.JSONField(default=list, blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_expenses",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date", "-created_at"]
        indexes = [
            models.Index(fields=["organization", "date"]),
            models.Index(fields=["user", "date"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return f"{self.description[:50]} - {self.currency} {self.amount}"


class Receipt(models.Model):
    """
    Receipt attachments for expenses.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    expense = models.ForeignKey(
        Expense, on_delete=models.CASCADE, related_name="receipts"
    )
    file = models.FileField(upload_to="receipts/%Y/%m/")
    filename = models.CharField(max_length=255)
    file_size = models.PositiveIntegerField(
        help_text="File size in bytes"
    )
    content_type = models.CharField(max_length=100)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="uploaded_receipts",
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-uploaded_at"]

    def __str__(self):
        return f"Receipt: {self.filename} for {self.expense}"
