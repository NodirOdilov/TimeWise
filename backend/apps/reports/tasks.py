"""
Celery tasks for the reports app.
"""

import logging
from datetime import timedelta

from celery import shared_task
from django.utils import timezone
from django.contrib.auth import get_user_model

from apps.accounts.models import Organization

logger = logging.getLogger(__name__)
User = get_user_model()


@shared_task(name="apps.reports.tasks.generate_weekly_reports")
def generate_weekly_reports():
    """
    Generate weekly time, project, and team reports for all organizations.
    Runs every Monday at 6 AM.
    """
    from .services import ReportService
    from apps.projects.models import Project

    today = timezone.now().date()
    week_end = today - timedelta(days=1)  # Sunday
    week_start = week_end - timedelta(days=6)  # Previous Monday

    organizations = Organization.objects.filter(is_active=True)

    reports_generated = 0
    for org in organizations:
        try:
            # Organization-wide time report
            ReportService.generate_time_report(
                organization=org,
                period_start=week_start,
                period_end=week_end,
            )
            reports_generated += 1

            # Per-user time reports
            active_users = User.objects.filter(
                organization=org, is_active=True
            )
            for user in active_users:
                ReportService.generate_time_report(
                    organization=org,
                    period_start=week_start,
                    period_end=week_end,
                    user=user,
                )
                reports_generated += 1

            # Active project reports
            active_projects = Project.objects.filter(
                organization=org,
                status=Project.Status.ACTIVE,
            )
            for project in active_projects:
                ReportService.generate_project_report(
                    project=project,
                    period_start=week_start,
                    period_end=week_end,
                )
                reports_generated += 1

            # Team report
            ReportService.generate_team_report(
                organization=org,
                period_start=week_start,
                period_end=week_end,
            )
            reports_generated += 1

        except Exception as e:
            logger.error(
                "Failed to generate weekly reports for org %s: %s",
                org.name,
                str(e),
            )

    logger.info("Generated %d weekly reports", reports_generated)
    return reports_generated
