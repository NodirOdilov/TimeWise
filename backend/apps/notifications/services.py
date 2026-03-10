"""
Notification service for creating and delivering notifications.
"""

import logging
from datetime import timedelta

from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone

from .models import Notification, NotificationPreference

logger = logging.getLogger(__name__)

# Mapping from notification types to preference fields
TYPE_TO_PREFERENCE = {
    "time_reminder": "time_reminders",
    "timesheet_reminder": "timesheet_reminders",
    "timesheet_approved": "approval_updates",
    "timesheet_rejected": "approval_updates",
    "expense_approved": "approval_updates",
    "expense_rejected": "approval_updates",
    "invoice_sent": "invoice_updates",
    "invoice_paid": "invoice_updates",
    "invoice_overdue": "invoice_updates",
    "budget_alert": "budget_alerts",
    "project_assigned": "project_updates",
    "task_assigned": "task_assignments",
    "mention": "system_notifications",
    "system": "system_notifications",
}


class NotificationService:
    """Service for creating and managing notifications."""

    @staticmethod
    def create_notification(
        user,
        notification_type,
        title,
        message,
        priority="normal",
        action_url="",
        metadata=None,
        send_email_override=None,
    ):
        """
        Create a notification and optionally send an email.
        Respects user notification preferences.
        """
        if metadata is None:
            metadata = {}

        prefs = NotificationService._get_preferences(user)
        pref_field = TYPE_TO_PREFERENCE.get(notification_type, "system_notifications")
        channel = getattr(prefs, pref_field, "in_app") if prefs else "in_app"

        if channel == "none" and send_email_override is None:
            return None

        notification = None
        if channel in ("in_app", "both") or send_email_override is False:
            notification = Notification.objects.create(
                user=user,
                notification_type=notification_type,
                priority=priority,
                title=title,
                message=message,
                action_url=action_url,
                metadata=metadata,
                expires_at=timezone.now() + timedelta(days=30),
            )

        should_email = (
            send_email_override
            if send_email_override is not None
            else channel in ("email", "both")
        )

        if should_email and user.email:
            if not NotificationService._is_quiet_hours(user, prefs):
                NotificationService._send_email_notification(
                    user=user,
                    title=title,
                    message=message,
                    action_url=action_url,
                )

        return notification

    @staticmethod
    def mark_all_read(user):
        """Mark all unread notifications as read for a user."""
        now = timezone.now()
        count = Notification.objects.filter(
            user=user, is_read=False
        ).update(is_read=True, read_at=now)
        return count

    @staticmethod
    def get_unread_count(user):
        """Get the count of unread notifications for a user."""
        return Notification.objects.filter(
            user=user, is_read=False
        ).count()

    @staticmethod
    def cleanup_expired_notifications():
        """Delete expired notifications."""
        count, _ = Notification.objects.filter(
            expires_at__lt=timezone.now()
        ).delete()
        logger.info("Cleaned up %d expired notifications", count)
        return count

    @staticmethod
    def _get_preferences(user):
        """Get or create notification preferences for a user."""
        prefs, _ = NotificationPreference.objects.get_or_create(user=user)
        return prefs

    @staticmethod
    def _is_quiet_hours(user, prefs):
        """Check if the current time falls within the user's quiet hours."""
        if not prefs or not prefs.quiet_hours_start or not prefs.quiet_hours_end:
            return False

        import pytz

        user_tz = pytz.timezone(user.timezone or "UTC")
        now_user = timezone.now().astimezone(user_tz).time()

        start = prefs.quiet_hours_start
        end = prefs.quiet_hours_end

        if start <= end:
            return start <= now_user <= end
        else:
            return now_user >= start or now_user <= end

    @staticmethod
    def _send_email_notification(user, title, message, action_url=""):
        """Send an email notification."""
        try:
            email_body = f"Hi {user.first_name},\n\n{message}"
            if action_url:
                email_body += f"\n\nView details: {action_url}"
            email_body += f"\n\nBest regards,\nTimeWise Team"

            send_mail(
                subject=f"[TimeWise] {title}",
                message=email_body,
                from_email=None,
                recipient_list=[user.email],
                fail_silently=True,
            )
        except Exception as e:
            logger.error(
                "Failed to send email notification to %s: %s",
                user.email,
                str(e),
            )
