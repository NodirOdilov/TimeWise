"""
Business logic services for generating reports.
"""

import logging
from datetime import timedelta, date
from decimal import Decimal

from django.db.models import Sum, Count, Q, F, Avg
from django.utils import timezone
from django.contrib.auth import get_user_model

from apps.time_entries.models import TimeEntry
from apps.projects.models import Project
from apps.invoicing.models import Invoice
from apps.expenses.models import Expense
from .models import TimeReport, ProjectReport, TeamReport

logger = logging.getLogger(__name__)
User = get_user_model()


class ReportService:
    """Service for generating various reports."""

    @staticmethod
    def generate_time_report(organization, period_start, period_end, user=None):
        """
        Generate a time tracking report for a date range.
        """
        filters = {
            "organization": organization,
            "date__gte": period_start,
            "date__lte": period_end,
            "is_running": False,
        }
        if user:
            filters["user"] = user

        entries = TimeEntry.objects.filter(**filters)

        total_minutes = entries.aggregate(
            total=Sum("duration_minutes")
        )["total"] or 0
        billable_minutes = entries.filter(
            is_billable=True
        ).aggregate(total=Sum("duration_minutes"))["total"] or 0
        non_billable_minutes = total_minutes - billable_minutes

        billable_amount = entries.filter(
            is_billable=True
        ).aggregate(total=Sum("billable_amount"))["total"] or Decimal("0.00")
        cost_amount = entries.aggregate(
            total=Sum("cost_amount")
        )["total"] or Decimal("0.00")

        # Calculate utilization
        if user:
            working_days = ReportService._count_working_days(
                period_start, period_end, organization
            )
            capacity_minutes = working_days * float(organization.work_hours_per_day) * 60
        else:
            active_users = User.objects.filter(
                organization=organization, is_active=True
            ).count()
            working_days = ReportService._count_working_days(
                period_start, period_end, organization
            )
            capacity_minutes = (
                working_days * float(organization.work_hours_per_day) * 60 * active_users
            )

        utilization = (
            (billable_minutes / capacity_minutes * 100)
            if capacity_minutes > 0
            else 0
        )

        # Breakdown by project
        project_breakdown = {}
        project_entries = entries.values(
            "project__id", "project__name"
        ).annotate(
            hours=Sum("duration_minutes"),
            amount=Sum("billable_amount"),
        ).order_by("-hours")

        for pe in project_entries:
            project_name = pe["project__name"] or "No Project"
            project_breakdown[project_name] = {
                "hours": round((pe["hours"] or 0) / 60, 2),
                "amount": str(pe["amount"] or 0),
            }

        # Breakdown by day
        day_breakdown = {}
        current = period_start
        while current <= period_end:
            day_entries = entries.filter(date=current)
            day_minutes = day_entries.aggregate(
                total=Sum("duration_minutes")
            )["total"] or 0
            day_breakdown[current.isoformat()] = round(day_minutes / 60, 2)
            current += timedelta(days=1)

        report = TimeReport.objects.create(
            organization=organization,
            user=user,
            period_start=period_start,
            period_end=period_end,
            total_hours=Decimal(str(round(total_minutes / 60, 2))),
            billable_hours=Decimal(str(round(billable_minutes / 60, 2))),
            non_billable_hours=Decimal(str(round(non_billable_minutes / 60, 2))),
            billable_amount=billable_amount,
            cost_amount=cost_amount,
            profit_amount=billable_amount - cost_amount,
            utilization_percent=Decimal(str(round(utilization, 2))),
            breakdown_by_project=project_breakdown,
            breakdown_by_day=day_breakdown,
        )

        return report

    @staticmethod
    def generate_project_report(project, period_start, period_end):
        """Generate a report for a specific project."""
        entries = TimeEntry.objects.filter(
            project=project,
            date__gte=period_start,
            date__lte=period_end,
            is_running=False,
        )

        total_minutes = entries.aggregate(
            total=Sum("duration_minutes")
        )["total"] or 0
        billable_minutes = entries.filter(
            is_billable=True
        ).aggregate(total=Sum("duration_minutes"))["total"] or 0
        billable_amount = entries.filter(
            is_billable=True
        ).aggregate(total=Sum("billable_amount"))["total"] or Decimal("0.00")
        cost_amount = entries.aggregate(
            total=Sum("cost_amount")
        )["total"] or Decimal("0.00")

        profit_margin = (
            ((billable_amount - cost_amount) / billable_amount * 100)
            if billable_amount > 0
            else Decimal("0")
        )

        # Member breakdown
        member_stats = entries.values(
            "user__id", "user__first_name", "user__last_name"
        ).annotate(
            total_minutes=Sum("duration_minutes"),
            total_amount=Sum("billable_amount"),
        ).order_by("-total_minutes")

        hours_by_member = {}
        for ms in member_stats:
            name = f"{ms['user__first_name']} {ms['user__last_name']}"
            hours_by_member[name] = {
                "hours": round((ms["total_minutes"] or 0) / 60, 2),
                "amount": str(ms["total_amount"] or 0),
            }

        # Task breakdown
        task_stats = entries.values(
            "task__id", "task__name"
        ).annotate(
            total_minutes=Sum("duration_minutes"),
        ).order_by("-total_minutes")

        hours_by_task = {}
        for ts in task_stats:
            task_name = ts["task__name"] or "No Task"
            hours_by_task[task_name] = round((ts["total_minutes"] or 0) / 60, 2)

        # Budget info
        budget = project.budgets.filter(is_active=True).first()
        budget_total = budget.amount if budget else Decimal("0")
        budget_spent = budget.spent_amount if budget else Decimal("0")

        # Expenses
        expense_total = Expense.objects.filter(
            project=project,
            date__gte=period_start,
            date__lte=period_end,
            status__in=[Expense.Status.APPROVED, Expense.Status.INVOICED],
        ).aggregate(total=Sum("amount"))["total"] or Decimal("0.00")

        # Invoice info
        invoiced = Invoice.objects.filter(
            project=project,
            issue_date__gte=period_start,
            issue_date__lte=period_end,
        ).aggregate(
            total=Sum("total_amount"),
            outstanding=Sum("amount_due"),
        )

        report = ProjectReport.objects.create(
            organization=project.organization,
            project=project,
            period_start=period_start,
            period_end=period_end,
            total_hours=Decimal(str(round(total_minutes / 60, 2))),
            billable_hours=Decimal(str(round(billable_minutes / 60, 2))),
            billable_amount=billable_amount,
            cost_amount=cost_amount,
            profit_margin_percent=profit_margin,
            budget_spent=budget_spent,
            budget_total=budget_total,
            budget_utilization_percent=(
                (budget_spent / budget_total * 100) if budget_total > 0 else 0
            ),
            hours_by_member=hours_by_member,
            hours_by_task=hours_by_task,
            expense_total=expense_total,
            invoiced_amount=invoiced["total"] or Decimal("0"),
            outstanding_amount=invoiced["outstanding"] or Decimal("0"),
        )

        return report

    @staticmethod
    def generate_team_report(organization, period_start, period_end, team=None):
        """Generate a report for a team or all teams."""
        if team:
            user_ids = team.members.values_list("id", flat=True)
        else:
            user_ids = User.objects.filter(
                organization=organization, is_active=True
            ).values_list("id", flat=True)

        entries = TimeEntry.objects.filter(
            user_id__in=user_ids,
            date__gte=period_start,
            date__lte=period_end,
            is_running=False,
        )

        total_minutes = entries.aggregate(
            total=Sum("duration_minutes")
        )["total"] or 0
        billable_minutes = entries.filter(
            is_billable=True
        ).aggregate(total=Sum("duration_minutes"))["total"] or 0
        billable_amount = entries.filter(
            is_billable=True
        ).aggregate(total=Sum("billable_amount"))["total"] or Decimal("0.00")
        cost_amount = entries.aggregate(
            total=Sum("cost_amount")
        )["total"] or Decimal("0.00")

        # Capacity
        member_count = len(user_ids)
        working_days = ReportService._count_working_days(
            period_start, period_end, organization
        )
        capacity_hours = (
            working_days * float(organization.work_hours_per_day) * member_count
        )
        utilization = (
            (total_minutes / 60 / capacity_hours * 100)
            if capacity_hours > 0
            else 0
        )

        # Member breakdown
        member_stats = entries.values(
            "user__id", "user__first_name", "user__last_name"
        ).annotate(
            total_minutes=Sum("duration_minutes"),
            billable_minutes=Sum(
                "duration_minutes",
                filter=Q(is_billable=True),
            ),
        ).order_by("-total_minutes")

        member_breakdown = {}
        for ms in member_stats:
            name = f"{ms['user__first_name']} {ms['user__last_name']}"
            individual_capacity = working_days * float(organization.work_hours_per_day)
            individual_hours = (ms["total_minutes"] or 0) / 60
            member_breakdown[name] = {
                "total_hours": round(individual_hours, 2),
                "billable_hours": round((ms["billable_minutes"] or 0) / 60, 2),
                "utilization": round(
                    (individual_hours / individual_capacity * 100)
                    if individual_capacity > 0
                    else 0,
                    1,
                ),
            }

        # Project breakdown
        project_stats = entries.values(
            "project__name"
        ).annotate(
            total_minutes=Sum("duration_minutes"),
        ).order_by("-total_minutes")

        project_breakdown = {}
        for ps in project_stats:
            project_name = ps["project__name"] or "No Project"
            project_breakdown[project_name] = round(
                (ps["total_minutes"] or 0) / 60, 2
            )

        report = TeamReport.objects.create(
            organization=organization,
            team=team,
            period_start=period_start,
            period_end=period_end,
            total_hours=Decimal(str(round(total_minutes / 60, 2))),
            billable_hours=Decimal(str(round(billable_minutes / 60, 2))),
            capacity_hours=Decimal(str(round(capacity_hours, 2))),
            utilization_percent=Decimal(str(round(utilization, 2))),
            billable_amount=billable_amount,
            cost_amount=cost_amount,
            member_breakdown=member_breakdown,
            project_breakdown=project_breakdown,
        )

        return report

    @staticmethod
    def _count_working_days(start_date, end_date, organization):
        """Count working days in a date range based on org settings."""
        work_days_per_week = organization.work_days_per_week
        total_days = (end_date - start_date).days + 1
        full_weeks = total_days // 7
        remaining_days = total_days % 7

        working_days = full_weeks * work_days_per_week
        current = end_date - timedelta(days=remaining_days - 1)
        for _ in range(remaining_days):
            if current.weekday() < work_days_per_week:
                working_days += 1
            current += timedelta(days=1)

        return working_days
