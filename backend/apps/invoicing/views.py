"""
Views for the invoicing app.
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter

from apps.accounts.permissions import IsOrganizationAdmin, IsManagerOrAbove
from .models import Invoice, InvoiceItem, Payment, PaymentMethod, TaxRate
from .serializers import (
    InvoiceSerializer,
    InvoiceCreateSerializer,
    InvoiceListSerializer,
    InvoiceItemSerializer,
    PaymentSerializer,
    PaymentCreateSerializer,
    PaymentMethodSerializer,
    TaxRateSerializer,
)
from .services import InvoiceService


class InvoiceViewSet(viewsets.ModelViewSet):
    """CRUD operations for invoices."""

    serializer_class = InvoiceSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = {
        "status": ["exact", "in"],
        "client": ["exact"],
        "project": ["exact"],
        "issue_date": ["gte", "lte"],
        "due_date": ["gte", "lte"],
    }
    search_fields = ["invoice_number", "reference", "client__name"]
    ordering_fields = ["issue_date", "due_date", "total_amount", "created_at"]
    ordering = ["-issue_date"]

    def get_queryset(self):
        return Invoice.objects.filter(
            organization=self.request.user.organization
        ).select_related("client", "project", "tax_rate", "created_by")

    def get_serializer_class(self):
        if self.action == "create":
            return InvoiceCreateSerializer
        if self.action == "list":
            return InvoiceListSerializer
        return InvoiceSerializer

    def perform_create(self, serializer):
        serializer.save(
            organization=self.request.user.organization,
            created_by=self.request.user,
        )

    @action(detail=True, methods=["post"])
    def send(self, request, pk=None):
        """Mark invoice as sent and optionally send email."""
        invoice = self.get_object()
        send_email = request.data.get("send_email", True)

        result = InvoiceService.send_invoice(
            invoice=invoice,
            send_email=send_email,
        )

        return Response(InvoiceSerializer(result).data)

    @action(detail=True, methods=["post"])
    def record_payment(self, request, pk=None):
        """Record a payment against this invoice."""
        invoice = self.get_object()
        serializer = PaymentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        payment = Payment.objects.create(
            invoice=invoice,
            recorded_by=request.user,
            **serializer.validated_data,
        )

        return Response(
            PaymentSerializer(payment).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"])
    def void(self, request, pk=None):
        """Void an invoice."""
        invoice = self.get_object()
        reason = request.data.get("reason", "")
        result = InvoiceService.void_invoice(invoice, reason)
        return Response(InvoiceSerializer(result).data)

    @action(detail=True, methods=["post"])
    def duplicate(self, request, pk=None):
        """Create a duplicate of this invoice."""
        invoice = self.get_object()
        new_invoice = InvoiceService.duplicate_invoice(
            invoice=invoice,
            user=request.user,
        )
        return Response(
            InvoiceSerializer(new_invoice).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"], url_path="add-time-entries")
    def add_time_entries(self, request, pk=None):
        """Add unbilled time entries to this invoice."""
        invoice = self.get_object()
        entry_ids = request.data.get("entry_ids", [])

        items = InvoiceService.add_time_entries_to_invoice(
            invoice=invoice,
            entry_ids=entry_ids,
        )

        return Response(
            InvoiceItemSerializer(items, many=True).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=False, methods=["get"])
    def summary(self, request):
        """Get invoice summary statistics."""
        from django.db.models import Sum, Count

        invoices = self.get_queryset()

        return Response({
            "total_invoices": invoices.count(),
            "draft": invoices.filter(status=Invoice.Status.DRAFT).count(),
            "sent": invoices.filter(status=Invoice.Status.SENT).count(),
            "overdue": invoices.filter(status=Invoice.Status.OVERDUE).count(),
            "paid": invoices.filter(status=Invoice.Status.PAID).count(),
            "total_outstanding": str(
                invoices.filter(
                    status__in=[Invoice.Status.SENT, Invoice.Status.OVERDUE]
                ).aggregate(total=Sum("amount_due"))["total"] or 0
            ),
            "total_paid_amount": str(
                invoices.filter(
                    status=Invoice.Status.PAID
                ).aggregate(total=Sum("total_amount"))["total"] or 0
            ),
        })


class PaymentMethodViewSet(viewsets.ModelViewSet):
    """CRUD operations for payment methods."""

    serializer_class = PaymentMethodSerializer

    def get_queryset(self):
        return PaymentMethod.objects.filter(
            organization=self.request.user.organization
        )

    def perform_create(self, serializer):
        serializer.save(organization=self.request.user.organization)


class TaxRateViewSet(viewsets.ModelViewSet):
    """CRUD operations for tax rates."""

    serializer_class = TaxRateSerializer

    def get_queryset(self):
        return TaxRate.objects.filter(
            organization=self.request.user.organization
        )

    def perform_create(self, serializer):
        serializer.save(organization=self.request.user.organization)
