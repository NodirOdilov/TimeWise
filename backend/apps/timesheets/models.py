"""
Timesheet models: WeeklyTimesheet and TimesheetApproval.
"""

import uuid
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models import Sum
from django.utils import timezone


class WeeklyTimesheet(models.Model):
    """
    A weekly timesheet aggregating time entries for a user.
    """

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        SUBMITTED = "submitted", "Submitted"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        LOCKED = "locked", "Locked"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="timesheets",
    )
    organization = models.ForeignKey(
        "accounts.Organization",
        on_delete=models.CASCADE,
        related_name="timesheets",
    )
    week_start = models.DateField(
        help_text="Monday of the week this timesheet covers"
    )
    week_end = models.DateField(
        help_text="Sunday of the week this timesheet covers"
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.OPEN
    )
    total_hours = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    billable_hours = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    non_billable_hours = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    overtime_hours = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    submitted_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-week_start"]
        unique_together = ["user", "week_start"]
        indexes = [
            models.Index(fields=["organization", "week_start"]),
            models.Index(fields=["user", "week_start"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return f"{self.user.full_name} - Week of {self.week_start}"

    def recalculate_totals(self):
        """Recalculate totals from linked time entries."""
        from apps.time_entries.models import TimeEntry

        entries = TimeEntry.objects.filter(
            user=self.user,
            date__gte=self.week_start,
            date__lte=self.week_end,
            is_running=False,
        )

        total_minutes = entries.aggregate(
            total=Sum("duration_minutes")
        )["total"] or 0
        billable_minutes = entries.filter(
            is_billable=True
        ).aggregate(total=Sum("duration_minutes"))["total"] or 0

        self.total_hours = Decimal(str(round(total_minutes / 60, 2)))
        self.billable_hours = Decimal(str(round(billable_minutes / 60, 2)))
        self.non_billable_hours = self.total_hours - self.billable_hours

        weekly_capacity = self.user.weekly_capacity_hours
        if self.total_hours > weekly_capacity:
            self.overtime_hours = self.total_hours - weekly_capacity
        else:
            self.overtime_hours = Decimal("0.00")

        self.save(update_fields=[
            "total_hours", "billable_hours",
            "non_billable_hours", "overtime_hours", "updated_at",
        ])


class TimesheetApproval(models.Model):
    """
    Approval records for weekly timesheets.
    """

    class Action(models.TextChoices):
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    timesheet = models.ForeignKey(
        WeeklyTimesheet,
        on_delete=models.CASCADE,
        related_name="approvals",
    )
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="timesheet_reviews",
    )
    action = models.CharField(max_length=10, choices=Action.choices)
    comment = models.TextField(blank=True, default="")
    reviewed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-reviewed_at"]

    def __str__(self):
        return f"{self.action} by {self.reviewer} on {self.reviewed_at}"
