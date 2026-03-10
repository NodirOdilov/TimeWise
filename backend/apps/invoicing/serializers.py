"""
Serializers for the invoicing app.
"""

from rest_framework import serializers

from .models import Invoice, InvoiceItem, Payment, PaymentMethod, TaxRate


class TaxRateSerializer(serializers.ModelSerializer):
    class Meta:
        model = TaxRate
        fields = [
            "id", "organization", "name", "rate", "description",
            "is_compound", "is_default", "is_active", "created_at",
        ]
        read_only_fields = ["id", "organization", "created_at"]


class PaymentMethodSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentMethod
        fields = [
            "id", "organization", "name", "method_type",
            "details", "is_default", "is_active", "created_at",
        ]
        read_only_fields = ["id", "organization", "created_at"]


class InvoiceItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = InvoiceItem
        fields = [
            "id", "invoice", "item_type", "description",
            "quantity", "unit_price", "total", "time_entry",
            "expense", "sort_order", "created_at",
        ]
        read_only_fields = ["id", "total", "created_at"]


class InvoiceItemCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = InvoiceItem
        fields = [
            "item_type", "description", "quantity",
            "unit_price", "time_entry", "expense", "sort_order",
        ]


class PaymentSerializer(serializers.ModelSerializer):
    recorded_by_name = serializers.CharField(
        source="recorded_by.full_name", read_only=True
    )
    payment_method_name = serializers.CharField(
        source="payment_method.name", read_only=True
    )

    class Meta:
        model = Payment
        fields = [
            "id", "invoice", "amount", "currency", "payment_method",
            "payment_method_name", "status", "payment_date",
            "reference", "notes", "recorded_by", "recorded_by_name",
            "created_at",
        ]
        read_only_fields = ["id", "recorded_by", "created_at"]


class PaymentCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = [
            "amount", "currency", "payment_method",
            "payment_date", "reference", "notes",
        ]

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Payment amount must be positive.")
        return value


class InvoiceSerializer(serializers.ModelSerializer):
    client_name = serializers.CharField(source="client.name", read_only=True)
    project_name = serializers.CharField(source="project.name", read_only=True)
    created_by_name = serializers.CharField(
        source="created_by.full_name", read_only=True
    )
    items = InvoiceItemSerializer(many=True, read_only=True)
    payments = PaymentSerializer(many=True, read_only=True)
    is_overdue = serializers.BooleanField(read_only=True)
    days_until_due = serializers.IntegerField(read_only=True)
    tax_rate_name = serializers.CharField(
        source="tax_rate.name", read_only=True
    )

    class Meta:
        model = Invoice
        fields = [
            "id", "organization", "client", "client_name",
            "project", "project_name", "invoice_number", "reference",
            "status", "issue_date", "due_date", "currency",
            "subtotal", "tax_amount", "discount_amount",
            "discount_percent", "total_amount", "amount_paid",
            "amount_due", "tax_rate", "tax_rate_name",
            "payment_method", "notes", "internal_notes",
            "terms", "footer", "sent_at", "viewed_at", "paid_at",
            "created_by", "created_by_name", "items", "payments",
            "is_overdue", "days_until_due",
            "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "organization", "invoice_number", "subtotal",
            "tax_amount", "total_amount", "amount_paid", "amount_due",
            "sent_at", "viewed_at", "paid_at", "created_by",
            "created_at", "updated_at",
        ]


class InvoiceCreateSerializer(serializers.ModelSerializer):
    items = InvoiceItemCreateSerializer(many=True, required=False)

    class Meta:
        model = Invoice
        fields = [
            "client", "project", "reference", "issue_date", "due_date",
            "currency", "discount_percent", "tax_rate",
            "payment_method", "notes", "terms", "footer", "items",
        ]

    def create(self, validated_data):
        items_data = validated_data.pop("items", [])
        invoice = Invoice(**validated_data)
        invoice.invoice_number = invoice.organization.get_next_invoice_number()
        invoice.save()

        for item_data in items_data:
            InvoiceItem.objects.create(invoice=invoice, **item_data)

        invoice.save()  # Recalculate totals
        return invoice


class InvoiceListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for list views."""

    client_name = serializers.CharField(source="client.name", read_only=True)
    is_overdue = serializers.BooleanField(read_only=True)

    class Meta:
        model = Invoice
        fields = [
            "id", "invoice_number", "client", "client_name",
            "status", "issue_date", "due_date", "currency",
            "total_amount", "amount_paid", "amount_due",
            "is_overdue", "created_at",
        ]
