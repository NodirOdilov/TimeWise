"""
Report models: TimeReport, ProjectReport, TeamReport.
These models store pre-computed report snapshots for performance.
"""

import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class TimeReport(models.Model):
    """
    Snapshot of time tracking data for a reporting period.
    """

    class Period(models.TextChoices):
        DAILY = "daily", "Daily"
        WEEKLY = "weekly", "Weekly"
        MONTHLY = "monthly", "Monthly"
        QUARTERLY = "quarterly", "Quarterly"
        YEARLY = "yearly", "Yearly"
        CUSTOM = "custom", "Custom"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "accounts.Organization",
        on_delete=models.CASCADE,
        related_name="time_reports",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="time_reports",
        help_text="If null, report covers all users in the org",
    )
    period = models.CharField(
        max_length=20, choices=Period.choices, default=Period.WEEKLY
    )
    period_start = models.DateField()
    period_end = models.DateField()
    total_hours = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    billable_hours = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    non_billable_hours = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    billable_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    cost_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    profit_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    utilization_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    breakdown_by_project = models.JSONField(
        default=dict, blank=True,
        help_text="Hours and amounts broken down by project",
    )
    breakdown_by_day = models.JSONField(
        default=dict, blank=True,
        help_text="Hours broken down by day of the period",
    )
    generated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-period_start"]
        indexes = [
            models.Index(fields=["organization", "period_start"]),
            models.Index(fields=["user", "period_start"]),
        ]

    def __str__(self):
        user_str = self.user.full_name if self.user else "All Users"
        return f"Time Report: {user_str} ({self.period_start} - {self.period_end})"


class ProjectReport(models.Model):
    """
    Snapshot of project-level reporting data.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "accounts.Organization",
        on_delete=models.CASCADE,
        related_name="project_reports",
    )
    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.CASCADE,
        related_name="reports",
    )
    period_start = models.DateField()
    period_end = models.DateField()
    total_hours = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    billable_hours = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    billable_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    cost_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    profit_margin_percent = models.DecimalField(
        max_digits=5, decimal_places=2, default=0
    )
    budget_spent = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    budget_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    budget_utilization_percent = models.DecimalField(
        max_digits=5, decimal_places=2, default=0
    )
    hours_by_member = models.JSONField(
        default=dict, blank=True,
        help_text="Hours logged by each team member",
    )
    hours_by_task = models.JSONField(
        default=dict, blank=True,
        help_text="Hours logged by each task",
    )
    expense_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    invoiced_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    outstanding_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    generated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-period_start"]
        indexes = [
            models.Index(fields=["project", "period_start"]),
        ]

    def __str__(self):
        return f"Project Report: {self.project.name} ({self.period_start} - {self.period_end})"


class TeamReport(models.Model):
    """
    Snapshot of team-level performance data.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "accounts.Organization",
        on_delete=models.CASCADE,
        related_name="team_reports",
    )
    team = models.ForeignKey(
        "accounts.Team",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="reports",
    )
    period_start = models.DateField()
    period_end = models.DateField()
    total_hours = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    billable_hours = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    capacity_hours = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        help_text="Total capacity hours for the team in this period",
    )
    utilization_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    billable_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    cost_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    member_breakdown = models.JSONField(
        default=dict, blank=True,
        help_text="Individual member stats within the team",
    )
    project_breakdown = models.JSONField(
        default=dict, blank=True,
        help_text="Team hours broken down by project",
    )
    generated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-period_start"]

    def __str__(self):
        team_name = self.team.name if self.team else "All Teams"
        return f"Team Report: {team_name} ({self.period_start} - {self.period_end})"
