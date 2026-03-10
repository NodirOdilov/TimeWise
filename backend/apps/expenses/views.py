"""
Views for the expenses app.
"""

from django.utils import timezone
from rest_framework import viewsets, status, parsers
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter

from .models import Expense, ExpenseCategory, Receipt
from .serializers import (
    ExpenseSerializer,
    ExpenseCreateSerializer,
    ExpenseCategorySerializer,
    ReceiptSerializer,
    ExpenseApprovalSerializer,
)


class ExpenseCategoryViewSet(viewsets.ModelViewSet):
    """CRUD operations for expense categories."""

    serializer_class = ExpenseCategorySerializer

    def get_queryset(self):
        return ExpenseCategory.objects.filter(
            organization=self.request.user.organization
        )

    def perform_create(self, serializer):
        serializer.save(organization=self.request.user.organization)


class ExpenseViewSet(viewsets.ModelViewSet):
    """CRUD operations for expenses."""

    serializer_class = ExpenseSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = {
        "project": ["exact"],
        "category": ["exact"],
        "date": ["exact", "gte", "lte"],
        "status": ["exact", "in"],
        "is_billable": ["exact"],
        "is_reimbursable": ["exact"],
        "user": ["exact"],
    }
    search_fields = ["description", "merchant", "notes"]
    ordering_fields = ["date", "amount", "created_at"]
    ordering = ["-date"]

    def get_queryset(self):
        queryset = Expense.objects.filter(
            organization=self.request.user.organization
        ).select_related("user", "project", "category", "approved_by")

        if not self.request.user.is_manager_or_above():
            queryset = queryset.filter(user=self.request.user)

        return queryset

    def get_serializer_class(self):
        if self.action == "create":
            return ExpenseCreateSerializer
        return ExpenseSerializer

    def perform_create(self, serializer):
        serializer.save(
            organization=self.request.user.organization,
            user=self.request.user,
        )

    @action(detail=True, methods=["post"], url_path="upload-receipt",
            parser_classes=[parsers.MultiPartParser])
    def upload_receipt(self, request, pk=None):
        """Upload a receipt for this expense."""
        expense = self.get_object()
        file = request.FILES.get("file")

        if not file:
            return Response(
                {"file": "No file provided."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        allowed_types = [
            "image/jpeg", "image/png", "image/gif",
            "application/pdf",
        ]
        if file.content_type not in allowed_types:
            return Response(
                {"file": f"Unsupported file type. Allowed: {', '.join(allowed_types)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        receipt = Receipt.objects.create(
            expense=expense,
            file=file,
            filename=file.name,
            file_size=file.size,
            content_type=file.content_type,
            uploaded_by=request.user,
        )

        return Response(
            ReceiptSerializer(receipt).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=False, methods=["post"])
    def submit(self, request):
        """Submit expenses for approval."""
        expense_ids = request.data.get("expense_ids", [])
        expenses = Expense.objects.filter(
            id__in=expense_ids,
            user=request.user,
            status=Expense.Status.DRAFT,
        )
        count = expenses.update(status=Expense.Status.SUBMITTED)

        return Response(
            {"detail": f"{count} expenses submitted for approval."},
            status=status.HTTP_200_OK,
        )

    @action(detail=False, methods=["post"])
    def approve(self, request):
        """Approve or reject expenses (managers only)."""
        if not request.user.is_manager_or_above():
            return Response(
                {"detail": "Only managers can approve expenses."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = ExpenseApprovalSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        action_str = serializer.validated_data["action"]
        expense_ids = serializer.validated_data["expense_ids"]

        expenses = Expense.objects.filter(
            id__in=expense_ids,
            organization=request.user.organization,
            status=Expense.Status.SUBMITTED,
        )

        now = timezone.now()
        for expense in expenses:
            expense.status = action_str
            expense.approved_by = request.user
            expense.approved_at = now
            expense.save(update_fields=[
                "status", "approved_by", "approved_at", "updated_at",
            ])

        return Response(
            {"detail": f"{expenses.count()} expenses {action_str}."},
            status=status.HTTP_200_OK,
        )

    @action(detail=False, methods=["get"])
    def summary(self, request):
        """Get expense summary statistics."""
        from django.db.models import Sum

        expenses = self.get_queryset()

        return Response({
            "total_count": expenses.count(),
            "total_amount": str(
                expenses.aggregate(total=Sum("amount"))["total"] or 0
            ),
            "pending_approval": expenses.filter(
                status=Expense.Status.SUBMITTED
            ).count(),
            "approved_amount": str(
                expenses.filter(
                    status=Expense.Status.APPROVED
                ).aggregate(total=Sum("amount"))["total"] or 0
            ),
            "reimbursable_amount": str(
                expenses.filter(
                    is_reimbursable=True,
                    status__in=[Expense.Status.APPROVED, Expense.Status.INVOICED],
                ).aggregate(total=Sum("amount"))["total"] or 0
            ),
        })
