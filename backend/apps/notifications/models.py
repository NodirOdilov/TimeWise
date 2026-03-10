"""
Notification models for in-app and email notifications.
"""

import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class Notification(models.Model):
    """
    In-app notification for users.
    """

    class NotificationType(models.TextChoices):
        TIME_REMINDER = "time_reminder", "Time Reminder"
        TIMESHEET_REMINDER = "timesheet_reminder", "Timesheet Reminder"
        TIMESHEET_APPROVED = "timesheet_approved", "Timesheet Approved"
        TIMESHEET_REJECTED = "timesheet_rejected", "Timesheet Rejected"
        INVOICE_SENT = "invoice_sent", "Invoice Sent"
        INVOICE_PAID = "invoice_paid", "Invoice Paid"
        INVOICE_OVERDUE = "invoice_overdue", "Invoice Overdue"
        EXPENSE_APPROVED = "expense_approved", "Expense Approved"
        EXPENSE_REJECTED = "expense_rejected", "Expense Rejected"
        BUDGET_ALERT = "budget_alert", "Budget Alert"
        PROJECT_ASSIGNED = "project_assigned", "Project Assigned"
        TASK_ASSIGNED = "task_assigned", "Task Assigned"
        MENTION = "mention", "Mention"
        SYSTEM = "system", "System"

    class Priority(models.TextChoices):
        LOW = "low", "Low"
        NORMAL = "normal", "Normal"
        HIGH = "high", "High"
        URGENT = "urgent", "Urgent"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    notification_type = models.CharField(
        max_length=30,
        choices=NotificationType.choices,
        default=NotificationType.SYSTEM,
    )
    priority = models.CharField(
        max_length=10,
        choices=Priority.choices,
        default=Priority.NORMAL,
    )
    title = models.CharField(max_length=255)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    action_url = models.CharField(
        max_length=500, blank=True, default="",
        help_text="URL to navigate to when notification is clicked",
    )
    metadata = models.JSONField(
        default=dict, blank=True,
        help_text="Additional data associated with this notification",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(
        null=True, blank=True,
        help_text="When this notification expires and should be cleaned up",
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "is_read"]),
            models.Index(fields=["user", "created_at"]),
            models.Index(fields=["notification_type"]),
        ]

    def __str__(self):
        return f"{self.notification_type}: {self.title} -> {self.user}"

    def mark_read(self):
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=["is_read", "read_at"])


class NotificationPreference(models.Model):
    """
    User preferences for notification delivery.
    """

    class Channel(models.TextChoices):
        IN_APP = "in_app", "In-App"
        EMAIL = "email", "Email"
        BOTH = "both", "Both"
        NONE = "none", "None"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notification_preferences",
    )
    time_reminders = models.CharField(
        max_length=10, choices=Channel.choices, default=Channel.IN_APP
    )
    timesheet_reminders = models.CharField(
        max_length=10, choices=Channel.choices, default=Channel.BOTH
    )
    approval_updates = models.CharField(
        max_length=10, choices=Channel.choices, default=Channel.BOTH
    )
    invoice_updates = models.CharField(
        max_length=10, choices=Channel.choices, default=Channel.EMAIL
    )
    budget_alerts = models.CharField(
        max_length=10, choices=Channel.choices, default=Channel.BOTH
    )
    project_updates = models.CharField(
        max_length=10, choices=Channel.choices, default=Channel.IN_APP
    )
    task_assignments = models.CharField(
        max_length=10, choices=Channel.choices, default=Channel.BOTH
    )
    system_notifications = models.CharField(
        max_length=10, choices=Channel.choices, default=Channel.IN_APP
    )
    quiet_hours_start = models.TimeField(
        null=True, blank=True,
        help_text="Start of quiet hours (no email notifications)",
    )
    quiet_hours_end = models.TimeField(
        null=True, blank=True,
        help_text="End of quiet hours",
    )

    def __str__(self):
        return f"Notification preferences for {self.user}"
