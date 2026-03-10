"""
Business logic services for time entries.
"""

import logging
from datetime import timedelta, date
from decimal import Decimal

from django.db import transaction
from django.db.models import Sum, Q
from django.utils import timezone

from apps.accounts.models import BillingRate
from .models import TimeEntry, Timer, TimeApproval

logger = logging.getLogger(__name__)


class TimerService:
    """Service for managing timers."""

    @staticmethod
    @transaction.atomic
    def start_timer(user, description="", project=None, task=None, is_billable=True):
        """
        Start a new timer for the user. Stops any existing timer first.
        """
        # Stop any running timer
        existing_timer = Timer.objects.filter(user=user).first()
        if existing_timer:
            TimerService.stop_timer(user)

        # Determine rates
        hourly_rate = Decimal("0.00")
        cost_rate = user.default_hourly_rate

        if is_billable:
            billing_rate = BillingRate.get_effective_rate(
                organization=user.organization,
                user=user,
                project=project,
            )
            if billing_rate:
                hourly_rate = billing_rate.rate
            elif user.organization:
                hourly_rate = user.organization.default_hourly_rate

        now = timezone.now()

        # Create the time entry
        time_entry = TimeEntry.objects.create(
            user=user,
            organization=user.organization,
            project=project,
            task=task,
            description=description,
            date=now.date(),
            start_time=now,
            entry_type=TimeEntry.EntryType.TIMER,
            is_billable=is_billable,
            is_running=True,
            hourly_rate=hourly_rate,
            cost_rate=cost_rate,
        )

        # Create the timer
        timer = Timer.objects.create(
            user=user,
            time_entry=time_entry,
            started_at=now,
            description=description,
            project=project,
            task=task,
        )

        return timer

    @staticmethod
    @transaction.atomic
    def stop_timer(user):
        """
        Stop the user's running timer and finalize the time entry.
        """
        try:
            timer = Timer.objects.select_related("time_entry").get(user=user)
        except Timer.DoesNotExist:
            return None

        time_entry = timer.time_entry
        now = timezone.now()

        # Update the time entry
        time_entry.end_time = now
        time_entry.is_running = False
        delta = now - timer.started_at
        time_entry.duration_minutes = max(1, int(delta.total_seconds() / 60))
        time_entry.save()

        # Delete the timer
        timer.delete()

        return time_entry

    @staticmethod
    def get_running_timer(user):
        """Get the user's currently running timer."""
        try:
            return Timer.objects.select_related(
                "time_entry", "project", "task"
            ).get(user=user)
        except Timer.DoesNotExist:
            return None

    @staticmethod
    @transaction.atomic
    def update_running_timer(user, description=None, project=None, task=None):
        """Update properties of a running timer."""
        try:
            timer = Timer.objects.select_related("time_entry").get(user=user)
        except Timer.DoesNotExist:
            return None

        if description is not None:
            timer.description = description
            timer.time_entry.description = description
        if project is not None:
            timer.project = project
            timer.time_entry.project = project
        if task is not None:
            timer.task = task
            timer.time_entry.task = task

        timer.save()
        timer.time_entry.save()
        return timer


class TimeEntryService:
    """Service for managing time entries."""

    @staticmethod
    def create_entry(user, data):
        """Create a new manual time entry."""
        project = data.get("project")
        is_billable = data.get("is_billable", True)

        # Determine rates
        hourly_rate = Decimal("0.00")
        cost_rate = user.default_hourly_rate

        if is_billable:
            billing_rate = BillingRate.get_effective_rate(
                organization=user.organization,
                user=user,
                project=project,
            )
            if billing_rate:
                hourly_rate = billing_rate.rate
            elif user.organization:
                hourly_rate = user.organization.default_hourly_rate

        entry = TimeEntry.objects.create(
            user=user,
            organization=user.organization,
            entry_type=TimeEntry.EntryType.MANUAL,
            hourly_rate=hourly_rate,
            cost_rate=cost_rate,
            **data,
        )
        return entry

    @staticmethod
    @transaction.atomic
    def bulk_create_entries(user, entries_data):
        """Create multiple time entries at once."""
        created = []
        for data in entries_data:
            entry = TimeEntryService.create_entry(user, data)
            created.append(entry)
        return created

    @staticmethod
    def get_weekly_summary(user, week_start):
        """
        Get a summary of time entries for a specific week.
        """
        week_end = week_start + timedelta(days=6)

        entries = TimeEntry.objects.filter(
            user=user,
            date__gte=week_start,
            date__lte=week_end,
            is_running=False,
        ).select_related("project", "task")

        # Calculate daily totals
        daily_totals = {}
        for i in range(7):
            day = week_start + timedelta(days=i)
            day_str = day.isoformat()
            day_entries = entries.filter(date=day)
            daily_totals[day_str] = {
                "total_minutes": day_entries.aggregate(
                    total=Sum("duration_minutes")
                )["total"] or 0,
                "billable_minutes": day_entries.filter(is_billable=True).aggregate(
                    total=Sum("duration_minutes")
                )["total"] or 0,
            }

        total_minutes = entries.aggregate(total=Sum("duration_minutes"))["total"] or 0
        billable_entries = entries.filter(is_billable=True)
        total_billable_minutes = billable_entries.aggregate(
            total=Sum("duration_minutes")
        )["total"] or 0
        total_billable_amount = billable_entries.aggregate(
            total=Sum("billable_amount")
        )["total"] or Decimal("0.00")

        return {
            "week_start": week_start,
            "week_end": week_end,
            "entries": entries,
            "total_minutes": total_minutes,
            "total_billable_minutes": total_billable_minutes,
            "total_billable_amount": total_billable_amount,
            "daily_totals": daily_totals,
        }

    @staticmethod
    @transaction.atomic
    def approve_entries(reviewer, entry_ids, action, comment=""):
        """
        Approve or reject multiple time entries.
        """
        entries = TimeEntry.objects.filter(
            id__in=entry_ids,
            organization=reviewer.organization,
            status=TimeEntry.Status.SUBMITTED,
        )

        new_status = (
            TimeEntry.Status.APPROVED
            if action == TimeApproval.Action.APPROVED
            else TimeEntry.Status.REJECTED
        )

        approvals = []
        for entry in entries:
            entry.status = new_status
            entry.save(update_fields=["status", "updated_at"])
            approval = TimeApproval.objects.create(
                time_entry=entry,
                reviewer=reviewer,
                action=action,
                comment=comment,
            )
            approvals.append(approval)

        return approvals

    @staticmethod
    def get_entries_for_date_range(user, start_date, end_date, project=None):
        """
        Get time entries for a date range, optionally filtered by project.
        """
        filters = {
            "user": user,
            "date__gte": start_date,
            "date__lte": end_date,
        }
        if project:
            filters["project"] = project

        return TimeEntry.objects.filter(**filters).select_related(
            "project", "task"
        ).order_by("date", "start_time")
