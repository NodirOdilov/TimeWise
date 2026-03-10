"""
Serializers for the expenses app.
"""

from rest_framework import serializers

from .models import Expense, ExpenseCategory, Receipt


class ExpenseCategorySerializer(serializers.ModelSerializer):
    expense_count = serializers.SerializerMethodField()

    class Meta:
        model = ExpenseCategory
        fields = [
            "id", "organization", "name", "description", "color",
            "is_billable_default", "is_active", "expense_count",
            "created_at",
        ]
        read_only_fields = ["id", "organization", "created_at"]

    def get_expense_count(self, obj):
        return obj.expenses.count()


class ReceiptSerializer(serializers.ModelSerializer):
    class Meta:
        model = Receipt
        fields = [
            "id", "expense", "file", "filename",
            "file_size", "content_type", "uploaded_by",
            "uploaded_at",
        ]
        read_only_fields = [
            "id", "filename", "file_size", "content_type",
            "uploaded_by", "uploaded_at",
        ]


class ExpenseSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source="user.full_name", read_only=True)
    project_name = serializers.CharField(source="project.name", read_only=True)
    category_name = serializers.CharField(source="category.name", read_only=True)
    approved_by_name = serializers.CharField(
        source="approved_by.full_name", read_only=True
    )
    receipts = ReceiptSerializer(many=True, read_only=True)

    class Meta:
        model = Expense
        fields = [
            "id", "organization", "user", "user_name",
            "project", "project_name", "category", "category_name",
            "description", "amount", "currency", "date",
            "is_billable", "is_reimbursable", "status",
            "merchant", "reference_number", "invoice",
            "notes", "tags", "approved_by", "approved_by_name",
            "approved_at", "receipts",
            "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "organization", "user", "status",
            "approved_by", "approved_at", "invoice",
            "created_at", "updated_at",
        ]


class ExpenseCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Expense
        fields = [
            "project", "category", "description", "amount",
            "currency", "date", "is_billable", "is_reimbursable",
            "merchant", "reference_number", "notes", "tags",
        ]

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Expense amount must be positive.")
        return value


class ExpenseApprovalSerializer(serializers.Serializer):
    action = serializers.ChoiceField(
        choices=[("approved", "Approved"), ("rejected", "Rejected")]
    )
    comment = serializers.CharField(required=False, default="", allow_blank=True)
    expense_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=True,
        min_length=1,
    )
