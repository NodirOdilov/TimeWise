"""
Serializers for the time_entries app.
"""

from rest_framework import serializers
from django.utils import timezone

from .models import TimeEntry, Timer, TimeApproval


class TimeEntrySerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source="user.full_name", read_only=True)
    project_name = serializers.CharField(source="project.name", read_only=True)
    task_name = serializers.CharField(source="task.name", read_only=True)
    formatted_duration = serializers.CharField(read_only=True)
    duration_hours = serializers.FloatField(read_only=True)

    class Meta:
        model = TimeEntry
        fields = [
            "id", "user", "user_name", "organization", "project",
            "project_name", "task", "task_name", "description",
            "date", "start_time", "end_time", "duration_minutes",
            "duration_hours", "formatted_duration", "entry_type",
            "is_billable", "is_running", "hourly_rate", "billable_amount",
            "cost_rate", "cost_amount", "status", "invoice",
            "tags", "notes", "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "user", "organization", "is_running",
            "billable_amount", "cost_amount", "created_at", "updated_at",
        ]


class TimeEntryCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = TimeEntry
        fields = [
            "project", "task", "description", "date",
            "start_time", "end_time", "duration_minutes",
            "is_billable", "tags", "notes",
        ]

    def validate(self, attrs):
        start_time = attrs.get("start_time")
        end_time = attrs.get("end_time")
        duration = attrs.get("duration_minutes", 0)

        if start_time and end_time:
            if end_time <= start_time:
                raise serializers.ValidationError(
                    {"end_time": "End time must be after start time."}
                )
            # Auto-calculate duration from times
            delta = end_time - start_time
            attrs["duration_minutes"] = int(delta.total_seconds() / 60)
        elif not duration and not (start_time and end_time):
            raise serializers.ValidationError(
                "Either duration_minutes or both start_time and end_time are required."
            )

        return attrs


class TimeEntryBulkCreateSerializer(serializers.Serializer):
    entries = TimeEntryCreateSerializer(many=True)


class TimerStartSerializer(serializers.Serializer):
    description = serializers.CharField(required=False, default="", allow_blank=True)
    project = serializers.UUIDField(required=False, allow_null=True)
    task = serializers.UUIDField(required=False, allow_null=True)
    is_billable = serializers.BooleanField(required=False, default=True)


class TimerSerializer(serializers.ModelSerializer):
    elapsed_seconds = serializers.IntegerField(read_only=True)
    elapsed_minutes = serializers.IntegerField(read_only=True)
    project_name = serializers.CharField(source="project.name", read_only=True)
    task_name = serializers.CharField(source="task.name", read_only=True)

    class Meta:
        model = Timer
        fields = [
            "id", "user", "time_entry", "started_at",
            "description", "project", "project_name",
            "task", "task_name", "elapsed_seconds",
            "elapsed_minutes", "created_at",
        ]
        read_only_fields = ["id", "user", "time_entry", "created_at"]


class TimerUpdateSerializer(serializers.Serializer):
    description = serializers.CharField(required=False, allow_blank=True)
    project = serializers.UUIDField(required=False, allow_null=True)
    task = serializers.UUIDField(required=False, allow_null=True)


class TimeApprovalSerializer(serializers.ModelSerializer):
    reviewer_name = serializers.CharField(source="reviewer.full_name", read_only=True)

    class Meta:
        model = TimeApproval
        fields = [
            "id", "time_entry", "reviewer", "reviewer_name",
            "action", "comment", "reviewed_at",
        ]
        read_only_fields = ["id", "reviewer", "reviewed_at"]


class TimeApprovalActionSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=TimeApproval.Action.choices)
    comment = serializers.CharField(required=False, default="", allow_blank=True)
    entry_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=True,
        min_length=1,
    )


class WeeklyTimesheetSerializer(serializers.Serializer):
    """Serializer for weekly timesheet data."""
    week_start = serializers.DateField()
    week_end = serializers.DateField()
    entries = TimeEntrySerializer(many=True)
    total_minutes = serializers.IntegerField()
    total_billable_minutes = serializers.IntegerField()
    total_billable_amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    daily_totals = serializers.DictField()
