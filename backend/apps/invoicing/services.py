"""
Business logic services for invoicing.
"""

import logging
from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)


class InvoiceService:
    """Service for invoice operations."""

    @staticmethod
    @transaction.atomic
    def send_invoice(invoice, send_email=True):
        """
        Mark an invoice as sent and optionally send notification email.
        """
        from .models import Invoice

        if invoice.status != Invoice.Status.DRAFT:
            from utils.exceptions import BusinessLogicError

            raise BusinessLogicError(
                f"Cannot send invoice with status '{invoice.status}'. "
                "Only draft invoices can be sent."
            )

        invoice.status = Invoice.Status.SENT
        invoice.sent_at = timezone.now()
        invoice.save(update_fields=["status", "sent_at", "updated_at"])

        if send_email:
            try:
                from django.core.mail import send_mail
                from django.template.loader import render_to_string

                send_mail(
                    subject=f"Invoice {invoice.invoice_number} from {invoice.organization.name}",
                    message=(
                        f"Dear {invoice.client.contact_name or invoice.client.name},\n\n"
                        f"Please find attached invoice {invoice.invoice_number} "
                        f"for {invoice.currency} {invoice.total_amount}.\n\n"
                        f"Due Date: {invoice.due_date.strftime('%B %d, %Y')}\n\n"
                        f"Thank you for your business.\n\n"
                        f"{invoice.organization.name}"
                    ),
                    from_email=None,
                    recipient_list=[invoice.client.contact_email],
                    fail_silently=True,
                )
                logger.info(
                    "Invoice %s sent to %s",
                    invoice.invoice_number,
                    invoice.client.contact_email,
                )
            except Exception as e:
                logger.error(
                    "Failed to send invoice email for %s: %s",
                    invoice.invoice_number,
                    str(e),
                )

        return invoice

    @staticmethod
    @transaction.atomic
    def void_invoice(invoice, reason=""):
        """Void an invoice."""
        from .models import Invoice
        from utils.exceptions import InvoiceAlreadyPaidError

        if invoice.status == Invoice.Status.PAID:
            raise InvoiceAlreadyPaidError()

        # Release associated time entries back to approved status
        from apps.time_entries.models import TimeEntry

        TimeEntry.objects.filter(
            invoice=invoice
        ).update(
            invoice=None,
            status=TimeEntry.Status.APPROVED,
        )

        invoice.status = Invoice.Status.VOID
        invoice.internal_notes = (
            f"{invoice.internal_notes}\n"
            f"[Voided on {timezone.now().strftime('%Y-%m-%d')}: {reason}]"
        ).strip()
        invoice.save(update_fields=["status", "internal_notes", "updated_at"])

        logger.info("Invoice %s voided. Reason: %s", invoice.invoice_number, reason)
        return invoice

    @staticmethod
    @transaction.atomic
    def duplicate_invoice(invoice, user):
        """
        Create a duplicate of an existing invoice with new number and draft status.
        """
        from .models import Invoice, InvoiceItem

        new_invoice = Invoice.objects.create(
            organization=invoice.organization,
            client=invoice.client,
            project=invoice.project,
            invoice_number=invoice.organization.get_next_invoice_number(),
            reference="",
            status=Invoice.Status.DRAFT,
            issue_date=timezone.now().date(),
            due_date=timezone.now().date() + timedelta(
                days=invoice.client.payment_terms_days
            ),
            currency=invoice.currency,
            discount_percent=invoice.discount_percent,
            tax_rate=invoice.tax_rate,
            payment_method=invoice.payment_method,
            notes=invoice.notes,
            terms=invoice.terms,
            footer=invoice.footer,
            created_by=user,
        )

        for item in invoice.items.all():
            InvoiceItem.objects.create(
                invoice=new_invoice,
                item_type=item.item_type,
                description=item.description,
                quantity=item.quantity,
                unit_price=item.unit_price,
                sort_order=item.sort_order,
            )

        new_invoice.save()  # Recalculate totals
        return new_invoice

    @staticmethod
    @transaction.atomic
    def add_time_entries_to_invoice(invoice, entry_ids):
        """
        Add approved time entries to an invoice as line items.
        """
        from apps.time_entries.models import TimeEntry
        from .models import InvoiceItem

        entries = TimeEntry.objects.filter(
            id__in=entry_ids,
            organization=invoice.organization,
            status=TimeEntry.Status.APPROVED,
            is_billable=True,
            invoice__isnull=True,
        ).select_related("project", "task", "user")

        items = []
        sort_order = invoice.items.count()

        for entry in entries:
            description_parts = [
                f"{entry.user.full_name}",
                f"{entry.date.strftime('%m/%d/%Y')}",
                f"{entry.formatted_duration}",
            ]
            if entry.project:
                description_parts.insert(0, entry.project.name)
            if entry.description:
                description_parts.append(f"- {entry.description}")

            item = InvoiceItem.objects.create(
                invoice=invoice,
                item_type=InvoiceItem.ItemType.TIME,
                description=" | ".join(description_parts),
                quantity=Decimal(str(entry.duration_hours)),
                unit_price=entry.hourly_rate,
                time_entry=entry,
                sort_order=sort_order,
            )
            items.append(item)
            sort_order += 1

            entry.invoice = invoice
            entry.status = TimeEntry.Status.INVOICED
            entry.save(update_fields=["invoice", "status", "updated_at"])

        invoice.save()  # Recalculate totals
        return items

    @staticmethod
    def create_invoice_from_project(project, user, date_from=None, date_to=None):
        """
        Create an invoice from all unbilled time on a project.
        """
        from apps.time_entries.models import TimeEntry
        from .models import Invoice

        filters = {
            "project": project,
            "is_billable": True,
            "status": TimeEntry.Status.APPROVED,
            "invoice__isnull": True,
        }
        if date_from:
            filters["date__gte"] = date_from
        if date_to:
            filters["date__lte"] = date_to

        entries = TimeEntry.objects.filter(**filters)

        if not entries.exists():
            return None

        invoice = Invoice.objects.create(
            organization=project.organization,
            client=project.client,
            project=project,
            invoice_number=project.organization.get_next_invoice_number(),
            status=Invoice.Status.DRAFT,
            issue_date=timezone.now().date(),
            due_date=timezone.now().date() + timedelta(
                days=project.client.payment_terms_days if project.client else 30
            ),
            currency=project.organization.default_currency,
            created_by=user,
        )

        InvoiceService.add_time_entries_to_invoice(
            invoice=invoice,
            entry_ids=list(entries.values_list("id", flat=True)),
        )

        return invoice
