"""
Time entry models: TimeEntry, Timer, and TimeApproval.
"""

import uuid
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone


class TimeEntry(models.Model):
    """
    A time entry represents a block of tracked time, either from a timer
    or manual entry.
    """

    class EntryType(models.TextChoices):
        TIMER = "timer", "Timer"
        MANUAL = "manual", "Manual Entry"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SUBMITTED = "submitted", "Submitted"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        INVOICED = "invoiced", "Invoiced"
        LOCKED = "locked", "Locked"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="time_entries",
    )
    organization = models.ForeignKey(
        "accounts.Organization",
        on_delete=models.CASCADE,
        related_name="time_entries",
    )
    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.CASCADE,
        related_name="time_entries",
        null=True,
        blank=True,
    )
    task = models.ForeignKey(
        "projects.Task",
        on_delete=models.SET_NULL,
        related_name="time_entries",
        null=True,
        blank=True,
    )
    description = models.TextField(blank=True, default="")
    date = models.DateField(default=timezone.now)
    start_time = models.DateTimeField(null=True, blank=True)
    end_time = models.DateTimeField(null=True, blank=True)
    duration_minutes = models.PositiveIntegerField(
        default=0,
        help_text="Duration in minutes. Auto-calculated for timer entries.",
    )
    entry_type = models.CharField(
        max_length=10, choices=EntryType.choices, default=EntryType.MANUAL
    )
    is_billable = models.BooleanField(default=True)
    is_running = models.BooleanField(
        default=False,
        help_text="True if the timer is currently running",
    )
    hourly_rate = models.DecimalField(
        max_digits=10, decimal_places=2, default=0.00,
        help_text="Billing rate applied to this entry",
    )
    billable_amount = models.DecimalField(
        max_digits=12, decimal_places=2, default=0.00,
        help_text="Calculated billable amount",
    )
    cost_rate = models.DecimalField(
        max_digits=10, decimal_places=2, default=0.00,
        help_text="Cost rate (user's internal rate) for profitability",
    )
    cost_amount = models.DecimalField(
        max_digits=12, decimal_places=2, default=0.00,
        help_text="Calculated cost amount",
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.DRAFT
    )
    invoice = models.ForeignKey(
        "invoicing.Invoice",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="time_entries",
    )
    tags = models.JSONField(default=list, blank=True)
    notes = models.TextField(blank=True, default="", help_text="Internal notes")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date", "-start_time"]
        verbose_name_plural = "Time entries"
        indexes = [
            models.Index(fields=["user", "date"]),
            models.Index(fields=["project", "date"]),
            models.Index(fields=["organization", "date"]),
            models.Index(fields=["status"]),
            models.Index(fields=["is_running"]),
        ]

    def __str__(self):
        return f"{self.user} - {self.date} - {self.duration_minutes}m"

    def save(self, *args, **kwargs):
        # Calculate duration from start/end times
        if self.start_time and self.end_time and not self.is_running:
            delta = self.end_time - self.start_time
            self.duration_minutes = int(delta.total_seconds() / 60)

        # Calculate billable amount
        if self.is_billable and self.hourly_rate > 0:
            hours = Decimal(str(self.duration_minutes)) / Decimal("60")
            self.billable_amount = (hours * self.hourly_rate).quantize(Decimal("0.01"))
        else:
            self.billable_amount = Decimal("0.00")

        # Calculate cost amount
        if self.cost_rate > 0:
            hours = Decimal(str(self.duration_minutes)) / Decimal("60")
            self.cost_amount = (hours * self.cost_rate).quantize(Decimal("0.01"))

        super().save(*args, **kwargs)

    @property
    def duration_hours(self):
        """Duration expressed in decimal hours."""
        return round(self.duration_minutes / 60, 2)

    @property
    def formatted_duration(self):
        """Duration formatted as HH:MM."""
        hours, minutes = divmod(self.duration_minutes, 60)
        return f"{hours:02d}:{minutes:02d}"


class Timer(models.Model):
    """
    Tracks currently running timers for users.
    Each user can have at most one running timer.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="active_timer",
    )
    time_entry = models.OneToOneField(
        TimeEntry,
        on_delete=models.CASCADE,
        related_name="timer",
    )
    started_at = models.DateTimeField(default=timezone.now)
    description = models.TextField(blank=True, default="")
    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    task = models.ForeignKey(
        "projects.Task",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-started_at"]

    def __str__(self):
        return f"Timer: {self.user} started at {self.started_at}"

    @property
    def elapsed_seconds(self):
        """Seconds elapsed since timer was started."""
        return int((timezone.now() - self.started_at).total_seconds())

    @property
    def elapsed_minutes(self):
        return self.elapsed_seconds // 60


class TimeApproval(models.Model):
    """
    Approval record for time entries.
    """

    class Action(models.TextChoices):
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    time_entry = models.ForeignKey(
        TimeEntry,
        on_delete=models.CASCADE,
        related_name="approvals",
    )
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="time_reviews",
    )
    action = models.CharField(max_length=10, choices=Action.choices)
    comment = models.TextField(blank=True, default="")
    reviewed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-reviewed_at"]

    def __str__(self):
        return f"{self.action} by {self.reviewer} on {self.reviewed_at}"
