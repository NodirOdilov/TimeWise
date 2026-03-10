"""
Celery tasks for the timesheets app.
"""

import logging
from datetime import timedelta

from celery import shared_task
from django.utils import timezone
from django.contrib.auth import get_user_model

logger = logging.getLogger(__name__)
User = get_user_model()


@shared_task(name="apps.timesheets.tasks.send_timesheet_reminders")
def send_timesheet_reminders():
    """
    Send reminders to users who haven't submitted their weekly timesheet.
    Runs on Fridays.
    """
    from .models import WeeklyTimesheet

    today = timezone.now().date()
    week_start = today - timedelta(days=today.weekday())

    active_users = User.objects.filter(
        is_active=True,
        organization__isnull=False,
    )

    reminded_count = 0
    for user in active_users:
        timesheet = WeeklyTimesheet.objects.filter(
            user=user,
            week_start=week_start,
        ).first()

        if not timesheet or timesheet.status == WeeklyTimesheet.Status.OPEN:
            try:
                from apps.notifications.services import NotificationService

                NotificationService.create_notification(
                    user=user,
                    notification_type="timesheet_reminder",
                    title="Weekly Timesheet Reminder",
                    message=(
                        f"Please submit your timesheet for the week of "
                        f"{week_start.strftime('%B %d, %Y')} before end of day."
                    ),
                )
                reminded_count += 1
            except Exception as e:
                logger.error(
                    "Failed to send timesheet reminder to %s: %s",
                    user.email,
                    str(e),
                )

    logger.info("Sent timesheet reminders to %d users", reminded_count)
    return reminded_count


@shared_task(name="apps.timesheets.tasks.auto_create_weekly_timesheets")
def auto_create_weekly_timesheets():
    """
    Auto-create weekly timesheet records for all active users on Monday.
    """
    from .models import WeeklyTimesheet

    today = timezone.now().date()
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)

    active_users = User.objects.filter(
        is_active=True,
        organization__isnull=False,
    )

    created_count = 0
    for user in active_users:
        _, created = WeeklyTimesheet.objects.get_or_create(
            user=user,
            week_start=week_start,
            defaults={
                "organization": user.organization,
                "week_end": week_end,
            },
        )
        if created:
            created_count += 1

    logger.info("Auto-created %d weekly timesheets", created_count)
    return created_count
