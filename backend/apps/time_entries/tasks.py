"""
Celery tasks for the time_entries app.
"""

import logging
from datetime import timedelta

from celery import shared_task
from django.utils import timezone
from django.contrib.auth import get_user_model

logger = logging.getLogger(__name__)
User = get_user_model()


@shared_task(name="apps.time_entries.tasks.auto_stop_stale_timers")
def auto_stop_stale_timers():
    """
    Automatically stop timers that have been running for more than 12 hours.
    This prevents accidental overnight timers from inflating time records.
    """
    from .models import Timer
    from .services import TimerService

    stale_threshold = timezone.now() - timedelta(hours=12)
    stale_timers = Timer.objects.filter(
        started_at__lt=stale_threshold
    ).select_related("user", "time_entry")

    stopped_count = 0
    for timer in stale_timers:
        try:
            time_entry = TimerService.stop_timer(timer.user)
            if time_entry:
                # Cap the duration at 12 hours
                time_entry.duration_minutes = 12 * 60
                time_entry.end_time = timer.started_at + timedelta(hours=12)
                time_entry.notes = (
                    f"{time_entry.notes}\n[Auto-stopped: Timer exceeded 12 hours]"
                ).strip()
                time_entry.save()
                stopped_count += 1
                logger.info(
                    "Auto-stopped stale timer for user %s (started %s)",
                    timer.user.email,
                    timer.started_at,
                )
        except Exception as e:
            logger.error(
                "Failed to auto-stop timer for user %s: %s",
                timer.user.email,
                str(e),
            )

    logger.info("Auto-stopped %d stale timers", stopped_count)
    return stopped_count


@shared_task(name="apps.time_entries.tasks.send_daily_time_reminder")
def send_daily_time_reminder():
    """
    Send a reminder to users who haven't logged any time today.
    """
    from .models import TimeEntry

    today = timezone.now().date()
    active_users = User.objects.filter(
        is_active=True,
        organization__isnull=False,
    )

    users_without_entries = []
    for user in active_users:
        has_entries = TimeEntry.objects.filter(
            user=user, date=today
        ).exists()
        if not has_entries:
            users_without_entries.append(user)

    for user in users_without_entries:
        try:
            from apps.notifications.services import NotificationService

            NotificationService.create_notification(
                user=user,
                notification_type="time_reminder",
                title="Don't forget to log your time!",
                message=f"You haven't logged any time entries for {today.strftime('%B %d, %Y')}.",
            )
        except Exception as e:
            logger.error(
                "Failed to send time reminder to %s: %s",
                user.email,
                str(e),
            )

    logger.info(
        "Sent daily time reminders to %d users",
        len(users_without_entries),
    )
    return len(users_without_entries)


@shared_task(name="apps.time_entries.tasks.calculate_weekly_totals")
def calculate_weekly_totals(user_id, week_start_str):
    """
    Calculate and cache weekly time totals for a user.
    """
    from datetime import datetime

    from django.core.cache import cache
    from .services import TimeEntryService

    try:
        user = User.objects.get(id=user_id)
        week_start = datetime.strptime(week_start_str, "%Y-%m-%d").date()
        summary = TimeEntryService.get_weekly_summary(user, week_start)

        cache_key = f"weekly_totals:{user_id}:{week_start_str}"
        cache_data = {
            "total_minutes": summary["total_minutes"],
            "total_billable_minutes": summary["total_billable_minutes"],
            "total_billable_amount": str(summary["total_billable_amount"]),
            "daily_totals": summary["daily_totals"],
        }
        cache.set(cache_key, cache_data, timeout=3600)
        return cache_data
    except User.DoesNotExist:
        logger.error("User %s not found for weekly totals calculation", user_id)
        return None
