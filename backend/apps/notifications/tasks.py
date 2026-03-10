"""
Celery tasks for the notifications app.
"""

import logging

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(name="apps.notifications.tasks.cleanup_expired_notifications")
def cleanup_expired_notifications():
    """
    Clean up expired notifications. Runs daily.
    """
    from .services import NotificationService

    count = NotificationService.cleanup_expired_notifications()
    logger.info("Cleaned up %d expired notifications", count)
    return count


@shared_task(name="apps.notifications.tasks.send_budget_alerts")
def send_budget_alerts():
    """
    Check all active project budgets and send alerts when thresholds are reached.
    """
    from apps.projects.models import ProjectBudget
    from .services import NotificationService

    budgets = ProjectBudget.objects.filter(
        is_active=True,
        project__status="active",
    ).select_related("project", "project__organization")

    alerts_sent = 0
    for budget in budgets:
        if budget.is_alert_threshold_reached:
            project = budget.project
            org = project.organization

            from django.contrib.auth import get_user_model

            User = get_user_model()

            managers = User.objects.filter(
                organization=org,
                is_active=True,
                role__in=["owner", "admin", "manager"],
            )

            for manager in managers:
                cache_key = f"budget_alert:{budget.id}:{manager.id}"

                from django.core.cache import cache

                if not cache.get(cache_key):
                    NotificationService.create_notification(
                        user=manager,
                        notification_type="budget_alert",
                        title=f"Budget Alert: {project.name}",
                        message=(
                            f"Project '{project.name}' has reached "
                            f"{budget.utilization_percent}% of its "
                            f"{budget.budget_type} budget "
                            f"({budget.currency} {budget.spent_amount} / "
                            f"{budget.currency} {budget.amount})."
                        ),
                        priority="high",
                        metadata={
                            "project_id": str(project.id),
                            "budget_id": str(budget.id),
                            "utilization_percent": budget.utilization_percent,
                        },
                    )
                    cache.set(cache_key, True, timeout=86400)
                    alerts_sent += 1

    logger.info("Sent %d budget alerts", alerts_sent)
    return alerts_sent


@shared_task(name="apps.notifications.tasks.send_overdue_invoice_notifications")
def send_overdue_invoice_notifications():
    """
    Send notifications for overdue invoices.
    """
    from apps.invoicing.models import Invoice
    from .services import NotificationService
    from django.contrib.auth import get_user_model

    User = get_user_model()

    overdue_invoices = Invoice.objects.filter(
        status__in=[Invoice.Status.SENT, Invoice.Status.VIEWED],
        due_date__lt=timezone.now().date(),
    ).select_related("organization", "client")

    notifications_sent = 0
    for invoice in overdue_invoices:
        if invoice.status != Invoice.Status.OVERDUE:
            invoice.status = Invoice.Status.OVERDUE
            invoice.save(update_fields=["status", "updated_at"])

        admins = User.objects.filter(
            organization=invoice.organization,
            is_active=True,
            role__in=["owner", "admin"],
        )

        days_overdue = (timezone.now().date() - invoice.due_date).days

        for admin in admins:
            NotificationService.create_notification(
                user=admin,
                notification_type="invoice_overdue",
                title=f"Invoice Overdue: {invoice.invoice_number}",
                message=(
                    f"Invoice {invoice.invoice_number} for {invoice.client.name} "
                    f"is {days_overdue} day(s) overdue. "
                    f"Amount due: {invoice.currency} {invoice.amount_due}"
                ),
                priority="high",
                metadata={
                    "invoice_id": str(invoice.id),
                    "invoice_number": invoice.invoice_number,
                    "days_overdue": days_overdue,
                },
            )
            notifications_sent += 1

    logger.info("Sent %d overdue invoice notifications", notifications_sent)
    return notifications_sent
