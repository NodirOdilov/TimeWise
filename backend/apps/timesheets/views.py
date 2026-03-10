"""
Views for the timesheets app.
"""

from datetime import datetime, timedelta

from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend

from apps.accounts.permissions import IsManagerOrAbove
from apps.time_entries.models import TimeEntry
from apps.time_entries.serializers import TimeEntrySerializer
from .models import WeeklyTimesheet, TimesheetApproval
from .serializers import (
    WeeklyTimesheetSerializer,
    WeeklyTimesheetDetailSerializer,
    TimesheetApprovalSerializer,
    TimesheetSubmitSerializer,
    TimesheetApprovalActionSerializer,
)


class WeeklyTimesheetViewSet(viewsets.ModelViewSet):
    """CRUD operations for weekly timesheets."""

    serializer_class = WeeklyTimesheetSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = {
        "status": ["exact", "in"],
        "week_start": ["exact", "gte", "lte"],
        "user": ["exact"],
    }

    def get_queryset(self):
        queryset = WeeklyTimesheet.objects.filter(
            organization=self.request.user.organization
        ).select_related("user")

        if not self.request.user.is_manager_or_above():
            queryset = queryset.filter(user=self.request.user)

        return queryset

    def get_serializer_class(self):
        if self.action == "retrieve":
            return WeeklyTimesheetDetailSerializer
        return WeeklyTimesheetSerializer

    @action(detail=False, methods=["get"], url_path="current")
    def current_week(self, request):
        """Get or create the timesheet for the current week."""
        today = timezone.now().date()
        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=6)

        user_id = request.query_params.get("user_id")
        if user_id and request.user.is_manager_or_above():
            from django.contrib.auth import get_user_model

            User = get_user_model()
            try:
                target_user = User.objects.get(
                    id=user_id,
                    organization=request.user.organization,
                )
            except User.DoesNotExist:
                return Response(
                    {"user_id": "User not found."},
                    status=status.HTTP_404_NOT_FOUND,
                )
        else:
            target_user = request.user

        timesheet, created = WeeklyTimesheet.objects.get_or_create(
            user=target_user,
            week_start=week_start,
            defaults={
                "organization": request.user.organization,
                "week_end": week_end,
            },
        )

        timesheet.recalculate_totals()

        entries = TimeEntry.objects.filter(
            user=target_user,
            date__gte=week_start,
            date__lte=week_end,
        ).select_related("project", "task").order_by("date", "start_time")

        data = WeeklyTimesheetDetailSerializer(timesheet).data
        data["entries"] = TimeEntrySerializer(entries, many=True).data

        return Response(data)

    @action(detail=True, methods=["post"])
    def submit(self, request, pk=None):
        """Submit a timesheet for approval."""
        timesheet = self.get_object()

        if timesheet.user != request.user:
            return Response(
                {"detail": "You can only submit your own timesheets."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if timesheet.status != WeeklyTimesheet.Status.OPEN:
            return Response(
                {"detail": f"Cannot submit a timesheet with status '{timesheet.status}'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        timesheet.recalculate_totals()
        timesheet.status = WeeklyTimesheet.Status.SUBMITTED
        timesheet.submitted_at = timezone.now()
        timesheet.save(update_fields=["status", "submitted_at", "updated_at"])

        # Also mark all draft time entries as submitted
        TimeEntry.objects.filter(
            user=timesheet.user,
            date__gte=timesheet.week_start,
            date__lte=timesheet.week_end,
            status=TimeEntry.Status.DRAFT,
        ).update(status=TimeEntry.Status.SUBMITTED)

        return Response(WeeklyTimesheetSerializer(timesheet).data)

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        """Approve or reject a timesheet (managers only)."""
        if not request.user.is_manager_or_above():
            return Response(
                {"detail": "Only managers can approve timesheets."},
                status=status.HTTP_403_FORBIDDEN,
            )

        timesheet = self.get_object()
        serializer = TimesheetApprovalActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        action_str = serializer.validated_data["action"]
        comment = serializer.validated_data.get("comment", "")

        if timesheet.status != WeeklyTimesheet.Status.SUBMITTED:
            return Response(
                {"detail": "Only submitted timesheets can be approved or rejected."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        new_status = (
            WeeklyTimesheet.Status.APPROVED
            if action_str == "approved"
            else WeeklyTimesheet.Status.REJECTED
        )
        timesheet.status = new_status
        timesheet.save(update_fields=["status", "updated_at"])

        # Update time entries
        entry_status = (
            TimeEntry.Status.APPROVED
            if action_str == "approved"
            else TimeEntry.Status.REJECTED
        )
        TimeEntry.objects.filter(
            user=timesheet.user,
            date__gte=timesheet.week_start,
            date__lte=timesheet.week_end,
            status=TimeEntry.Status.SUBMITTED,
        ).update(status=entry_status)

        approval = TimesheetApproval.objects.create(
            timesheet=timesheet,
            reviewer=request.user,
            action=action_str,
            comment=comment,
        )

        return Response(WeeklyTimesheetSerializer(timesheet).data)

    @action(detail=False, methods=["get"], url_path="pending")
    def pending_approval(self, request):
        """List timesheets pending approval."""
        if not request.user.is_manager_or_above():
            return Response(
                {"detail": "Only managers can view pending timesheets."},
                status=status.HTTP_403_FORBIDDEN,
            )

        timesheets = WeeklyTimesheet.objects.filter(
            organization=request.user.organization,
            status=WeeklyTimesheet.Status.SUBMITTED,
        ).select_related("user").order_by("week_start", "user__first_name")

        serializer = WeeklyTimesheetSerializer(timesheets, many=True)
        return Response(serializer.data)
