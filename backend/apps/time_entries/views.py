"""
Views for the time_entries app.
"""

from datetime import datetime, timedelta

from django.utils import timezone
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter

from .models import TimeEntry, Timer, TimeApproval
from .serializers import (
    TimeEntrySerializer,
    TimeEntryCreateSerializer,
    TimeEntryBulkCreateSerializer,
    TimerStartSerializer,
    TimerSerializer,
    TimerUpdateSerializer,
    TimeApprovalActionSerializer,
    TimeApprovalSerializer,
    WeeklyTimesheetSerializer,
)
from .services import TimerService, TimeEntryService


class TimeEntryViewSet(viewsets.ModelViewSet):
    """
    CRUD operations for time entries with timer support.
    """

    serializer_class = TimeEntrySerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = {
        "project": ["exact"],
        "task": ["exact"],
        "date": ["exact", "gte", "lte"],
        "status": ["exact", "in"],
        "is_billable": ["exact"],
        "is_running": ["exact"],
        "entry_type": ["exact"],
        "user": ["exact"],
    }
    search_fields = ["description", "notes", "tags"]
    ordering_fields = ["date", "start_time", "duration_minutes", "created_at"]
    ordering = ["-date", "-start_time"]

    def get_queryset(self):
        queryset = TimeEntry.objects.filter(
            organization=self.request.user.organization
        ).select_related("user", "project", "task")

        # Non-managers can only see their own entries
        if not self.request.user.is_manager_or_above():
            queryset = queryset.filter(user=self.request.user)

        return queryset

    def get_serializer_class(self):
        if self.action == "create":
            return TimeEntryCreateSerializer
        return TimeEntrySerializer

    def perform_create(self, serializer):
        TimeEntryService.create_entry(
            user=self.request.user,
            data=serializer.validated_data,
        )

    @action(detail=False, methods=["post"], url_path="start-timer")
    def start_timer(self, request):
        """Start a new timer."""
        serializer = TimerStartSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        from apps.projects.models import Project, Task

        project = None
        task = None
        project_id = serializer.validated_data.get("project")
        task_id = serializer.validated_data.get("task")

        if project_id:
            try:
                project = Project.objects.get(
                    id=project_id, organization=request.user.organization
                )
            except Project.DoesNotExist:
                return Response(
                    {"project": "Project not found."},
                    status=status.HTTP_404_NOT_FOUND,
                )

        if task_id:
            try:
                task = Task.objects.get(id=task_id)
            except Task.DoesNotExist:
                return Response(
                    {"task": "Task not found."},
                    status=status.HTTP_404_NOT_FOUND,
                )

        timer = TimerService.start_timer(
            user=request.user,
            description=serializer.validated_data.get("description", ""),
            project=project,
            task=task,
            is_billable=serializer.validated_data.get("is_billable", True),
        )

        return Response(
            TimerSerializer(timer).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=False, methods=["post"], url_path="stop-timer")
    def stop_timer(self, request):
        """Stop the running timer."""
        time_entry = TimerService.stop_timer(request.user)
        if time_entry is None:
            return Response(
                {"detail": "No running timer found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(TimeEntrySerializer(time_entry).data)

    @action(detail=False, methods=["get"], url_path="running")
    def running_timer(self, request):
        """Get the currently running timer."""
        timer = TimerService.get_running_timer(request.user)
        if timer is None:
            return Response(
                {"detail": "No running timer."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(TimerSerializer(timer).data)

    @action(detail=False, methods=["patch"], url_path="update-timer")
    def update_timer(self, request):
        """Update properties of the running timer."""
        serializer = TimerUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        from apps.projects.models import Project, Task

        project = None
        task = None
        project_id = serializer.validated_data.get("project")
        task_id = serializer.validated_data.get("task")

        if project_id:
            try:
                project = Project.objects.get(
                    id=project_id, organization=request.user.organization
                )
            except Project.DoesNotExist:
                return Response(
                    {"project": "Project not found."},
                    status=status.HTTP_404_NOT_FOUND,
                )
        if task_id:
            try:
                task = Task.objects.get(id=task_id)
            except Task.DoesNotExist:
                pass

        timer = TimerService.update_running_timer(
            user=request.user,
            description=serializer.validated_data.get("description"),
            project=project,
            task=task,
        )

        if timer is None:
            return Response(
                {"detail": "No running timer."},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(TimerSerializer(timer).data)

    @action(detail=False, methods=["post"], url_path="bulk-create")
    def bulk_create(self, request):
        """Create multiple time entries at once."""
        serializer = TimeEntryBulkCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        entries = TimeEntryService.bulk_create_entries(
            user=request.user,
            entries_data=serializer.validated_data["entries"],
        )

        return Response(
            TimeEntrySerializer(entries, many=True).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=False, methods=["get"], url_path="weekly")
    def weekly_summary(self, request):
        """Get weekly time entry summary."""
        date_str = request.query_params.get("week_start")
        if date_str:
            try:
                week_start = datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                return Response(
                    {"week_start": "Invalid date format. Use YYYY-MM-DD."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        else:
            today = timezone.now().date()
            week_start = today - timedelta(days=today.weekday())

        user_id = request.query_params.get("user_id")
        if user_id and request.user.is_manager_or_above():
            from django.contrib.auth import get_user_model
            User = get_user_model()
            try:
                target_user = User.objects.get(
                    id=user_id, organization=request.user.organization
                )
            except User.DoesNotExist:
                return Response(
                    {"user_id": "User not found."},
                    status=status.HTTP_404_NOT_FOUND,
                )
        else:
            target_user = request.user

        summary = TimeEntryService.get_weekly_summary(target_user, week_start)
        summary["entries"] = TimeEntrySerializer(summary["entries"], many=True).data

        return Response(summary)

    @action(detail=False, methods=["post"], url_path="submit")
    def submit_entries(self, request):
        """Submit time entries for approval."""
        entry_ids = request.data.get("entry_ids", [])
        entries = TimeEntry.objects.filter(
            id__in=entry_ids,
            user=request.user,
            status=TimeEntry.Status.DRAFT,
        )

        entries.update(status=TimeEntry.Status.SUBMITTED)

        return Response(
            {"detail": f"{entries.count()} entries submitted for approval."},
            status=status.HTTP_200_OK,
        )

    @action(detail=False, methods=["post"], url_path="approve")
    def approve_entries(self, request):
        """Approve or reject time entries (managers only)."""
        if not request.user.is_manager_or_above():
            return Response(
                {"detail": "Only managers can approve time entries."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = TimeApprovalActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        approvals = TimeEntryService.approve_entries(
            reviewer=request.user,
            entry_ids=serializer.validated_data["entry_ids"],
            action=serializer.validated_data["action"],
            comment=serializer.validated_data.get("comment", ""),
        )

        return Response(
            TimeApprovalSerializer(approvals, many=True).data,
            status=status.HTTP_200_OK,
        )

    @action(detail=False, methods=["get"], url_path="pending-approval")
    def pending_approval(self, request):
        """List entries pending approval for the manager."""
        if not request.user.is_manager_or_above():
            return Response(
                {"detail": "Only managers can view pending approvals."},
                status=status.HTTP_403_FORBIDDEN,
            )

        entries = TimeEntry.objects.filter(
            organization=request.user.organization,
            status=TimeEntry.Status.SUBMITTED,
        ).select_related("user", "project", "task").order_by("user", "date")

        page = self.paginate_queryset(entries)
        if page is not None:
            serializer = TimeEntrySerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = TimeEntrySerializer(entries, many=True)
        return Response(serializer.data)
