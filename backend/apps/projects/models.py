"""
Project models: Project, ProjectMember, ProjectBudget, Task, and Client.
"""

import uuid
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models import Sum
from django.utils import timezone


class Client(models.Model):
    """
    Client represents a customer or company that projects are billed to.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "accounts.Organization",
        on_delete=models.CASCADE,
        related_name="clients",
    )
    name = models.CharField(max_length=255)
    contact_name = models.CharField(max_length=255, blank=True, default="")
    contact_email = models.EmailField(blank=True, default="")
    contact_phone = models.CharField(max_length=30, blank=True, default="")
    address_line1 = models.CharField(max_length=255, blank=True, default="")
    address_line2 = models.CharField(max_length=255, blank=True, default="")
    city = models.CharField(max_length=100, blank=True, default="")
    state = models.CharField(max_length=100, blank=True, default="")
    postal_code = models.CharField(max_length=20, blank=True, default="")
    country = models.CharField(max_length=100, blank=True, default="")
    tax_id = models.CharField(max_length=50, blank=True, default="")
    currency = models.CharField(
        max_length=3,
        choices=settings.SUPPORTED_CURRENCIES,
        default=settings.DEFAULT_CURRENCY,
    )
    payment_terms_days = models.PositiveIntegerField(
        default=30,
        help_text="Default payment terms in days for this client",
    )
    notes = models.TextField(blank=True, default="")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        unique_together = ["organization", "name"]

    def __str__(self):
        return self.name

    @property
    def total_outstanding(self):
        """Total unpaid invoice amount for this client."""
        from apps.invoicing.models import Invoice

        return (
            Invoice.objects.filter(
                client=self,
                status__in=[Invoice.Status.SENT, Invoice.Status.OVERDUE],
            ).aggregate(total=Sum("total_amount"))["total"]
            or Decimal("0.00")
        )


class Project(models.Model):
    """
    Project is a container for time entries, tasks, and billing.
    """

    class Status(models.TextChoices):
        PLANNING = "planning", "Planning"
        ACTIVE = "active", "Active"
        ON_HOLD = "on_hold", "On Hold"
        COMPLETED = "completed", "Completed"
        ARCHIVED = "archived", "Archived"

    class BillingType(models.TextChoices):
        HOURLY = "hourly", "Hourly"
        FIXED = "fixed", "Fixed Price"
        NON_BILLABLE = "non_billable", "Non-Billable"
        RETAINER = "retainer", "Retainer"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "accounts.Organization",
        on_delete=models.CASCADE,
        related_name="projects",
    )
    client = models.ForeignKey(
        Client,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="projects",
    )
    name = models.CharField(max_length=255)
    code = models.CharField(
        max_length=20,
        blank=True,
        default="",
        help_text="Short project code (e.g., PROJ-001)",
    )
    description = models.TextField(blank=True, default="")
    color = models.CharField(
        max_length=7,
        default="#3B82F6",
        help_text="Hex color code for UI display",
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.ACTIVE
    )
    billing_type = models.CharField(
        max_length=20, choices=BillingType.choices, default=BillingType.HOURLY
    )
    hourly_rate = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00,
        help_text="Default hourly rate for this project",
    )
    fixed_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0.00,
        help_text="Fixed price for the project (if billing type is fixed)",
    )
    estimated_hours = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Estimated total hours for the project",
    )
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    is_billable = models.BooleanField(default=True)
    is_public = models.BooleanField(
        default=False,
        help_text="If true, all org members can view and log time",
    )
    tags = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        unique_together = ["organization", "name"]
        indexes = [
            models.Index(fields=["organization", "status"]),
            models.Index(fields=["client"]),
        ]

    def __str__(self):
        return f"{self.code or ''} {self.name}".strip()

    @property
    def total_logged_hours(self):
        """Total hours logged on this project."""
        total_minutes = self.time_entries.filter(
            is_running=False
        ).aggregate(total=Sum("duration_minutes"))["total"] or 0
        return round(total_minutes / 60, 2)

    @property
    def total_billable_amount(self):
        """Total billable amount for this project."""
        return (
            self.time_entries.filter(
                is_billable=True, is_running=False
            ).aggregate(total=Sum("billable_amount"))["total"]
            or Decimal("0.00")
        )

    @property
    def budget_utilization_percent(self):
        """Percentage of budget used based on estimated hours."""
        if self.estimated_hours and self.estimated_hours > 0:
            return round(
                (Decimal(str(self.total_logged_hours)) / self.estimated_hours) * 100, 1
            )
        return None


class ProjectMember(models.Model):
    """
    Associates users with projects and defines their project-level role.
    """

    class ProjectRole(models.TextChoices):
        PROJECT_MANAGER = "project_manager", "Project Manager"
        MEMBER = "member", "Member"
        VIEWER = "viewer", "Viewer"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name="members"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="project_memberships",
    )
    role = models.CharField(
        max_length=20,
        choices=ProjectRole.choices,
        default=ProjectRole.MEMBER,
    )
    hourly_rate = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Override hourly rate for this user on this project",
    )
    is_active = models.BooleanField(default=True)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ["project", "user"]
        ordering = ["joined_at"]

    def __str__(self):
        return f"{self.user} on {self.project} ({self.role})"


class ProjectBudget(models.Model):
    """
    Tracks budget allocations and spending for projects.
    """

    class BudgetType(models.TextChoices):
        TOTAL = "total", "Total Budget"
        MONTHLY = "monthly", "Monthly Budget"
        QUARTERLY = "quarterly", "Quarterly Budget"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name="budgets"
    )
    budget_type = models.CharField(
        max_length=20, choices=BudgetType.choices, default=BudgetType.TOTAL
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(
        max_length=3,
        choices=settings.SUPPORTED_CURRENCIES,
        default=settings.DEFAULT_CURRENCY,
    )
    hours_budget = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Budget in hours (alternative to monetary budget)",
    )
    period_start = models.DateField(null=True, blank=True)
    period_end = models.DateField(null=True, blank=True)
    alert_threshold_percent = models.PositiveIntegerField(
        default=80,
        help_text="Send alert when budget usage reaches this percentage",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.project.name} - {self.budget_type}: {self.currency} {self.amount}"

    @property
    def spent_amount(self):
        """Calculate total spent against this budget."""
        filters = {"project": self.project, "is_billable": True, "is_running": False}
        if self.period_start:
            filters["date__gte"] = self.period_start
        if self.period_end:
            filters["date__lte"] = self.period_end

        from apps.time_entries.models import TimeEntry

        return (
            TimeEntry.objects.filter(**filters).aggregate(
                total=Sum("billable_amount")
            )["total"]
            or Decimal("0.00")
        )

    @property
    def remaining_amount(self):
        return self.amount - self.spent_amount

    @property
    def utilization_percent(self):
        if self.amount > 0:
            return round((self.spent_amount / self.amount) * 100, 1)
        return 0

    @property
    def is_over_budget(self):
        return self.spent_amount > self.amount

    @property
    def is_alert_threshold_reached(self):
        return self.utilization_percent >= self.alert_threshold_percent


class Task(models.Model):
    """
    Tasks within a project that time can be logged against.
    """

    class Status(models.TextChoices):
        TODO = "todo", "To Do"
        IN_PROGRESS = "in_progress", "In Progress"
        IN_REVIEW = "in_review", "In Review"
        DONE = "done", "Done"
        CANCELLED = "cancelled", "Cancelled"

    class Priority(models.TextChoices):
        LOW = "low", "Low"
        MEDIUM = "medium", "Medium"
        HIGH = "high", "High"
        URGENT = "urgent", "Urgent"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name="tasks"
    )
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, default="")
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.TODO
    )
    priority = models.CharField(
        max_length=10, choices=Priority.choices, default=Priority.MEDIUM
    )
    assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_tasks",
    )
    estimated_hours = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True
    )
    due_date = models.DateField(null=True, blank=True)
    is_billable = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)
    tags = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sort_order", "created_at"]
        indexes = [
            models.Index(fields=["project", "status"]),
            models.Index(fields=["assignee"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.project.name})"

    @property
    def total_logged_hours(self):
        total_minutes = self.time_entries.filter(
            is_running=False
        ).aggregate(total=Sum("duration_minutes"))["total"] or 0
        return round(total_minutes / 60, 2)
