"""
Celery tasks for the invoicing app.
"""

import logging

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(name="apps.invoicing.tasks.check_overdue_invoices")
def check_overdue_invoices():
    """
    Check for overdue invoices and update their status.
    Runs daily at 9 AM.
    """
    from .models import Invoice

    today = timezone.now().date()
    overdue_invoices = Invoice.objects.filter(
        status__in=[Invoice.Status.SENT, Invoice.Status.VIEWED],
        due_date__lt=today,
    )

    count = 0
    for invoice in overdue_invoices:
        invoice.status = Invoice.Status.OVERDUE
        invoice.save(update_fields=["status", "updated_at"])
        count += 1

        try:
            from apps.notifications.tasks import send_overdue_invoice_notifications

            send_overdue_invoice_notifications.delay()
        except Exception as e:
            logger.error(
                "Failed to trigger overdue notification for invoice %s: %s",
                invoice.invoice_number,
                str(e),
            )

    logger.info("Marked %d invoices as overdue", count)
    return count


@shared_task(name="apps.invoicing.tasks.generate_recurring_invoices")
def generate_recurring_invoices():
    """
    Generate invoices for retainer projects on a monthly basis.
    """
    from apps.projects.models import Project
    from .services import InvoiceService

    retainer_projects = Project.objects.filter(
        billing_type=Project.BillingType.RETAINER,
        status=Project.Status.ACTIVE,
    ).select_related("organization", "client")

    generated_count = 0
    for project in retainer_projects:
        if not project.client:
            continue

        today = timezone.now().date()
        first_of_month = today.replace(day=1)

        from .models import Invoice

        existing = Invoice.objects.filter(
            project=project,
            issue_date__gte=first_of_month,
        ).exists()

        if not existing:
            try:
                from django.contrib.auth import get_user_model

                User = get_user_model()
                admin_user = User.objects.filter(
                    organization=project.organization,
                    role__in=["owner", "admin"],
                    is_active=True,
                ).first()

                if admin_user:
                    invoice = InvoiceService.create_invoice_from_project(
                        project=project,
                        user=admin_user,
                    )
                    if invoice:
                        generated_count += 1
                        logger.info(
                            "Generated recurring invoice %s for project %s",
                            invoice.invoice_number,
                            project.name,
                        )
            except Exception as e:
                logger.error(
                    "Failed to generate recurring invoice for %s: %s",
                    project.name,
                    str(e),
                )

    logger.info("Generated %d recurring invoices", generated_count)
    return generated_count
