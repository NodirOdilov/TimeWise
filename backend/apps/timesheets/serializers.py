"""
Serializers for the timesheets app.
"""

from rest_framework import serializers

from .models import WeeklyTimesheet, TimesheetApproval


class TimesheetApprovalSerializer(serializers.ModelSerializer):
    reviewer_name = serializers.CharField(
        source="reviewer.full_name", read_only=True
    )

    class Meta:
        model = TimesheetApproval
        fields = [
            "id", "timesheet", "reviewer", "reviewer_name",
            "action", "comment", "reviewed_at",
        ]
        read_only_fields = ["id", "reviewer", "reviewed_at"]


class WeeklyTimesheetSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source="user.full_name", read_only=True)
    user_email = serializers.CharField(source="user.email", read_only=True)

    class Meta:
        model = WeeklyTimesheet
        fields = [
            "id", "user", "user_name", "user_email",
            "organization", "week_start", "week_end",
            "status", "total_hours", "billable_hours",
            "non_billable_hours", "overtime_hours",
            "submitted_at", "notes",
            "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "user", "organization",
            "total_hours", "billable_hours",
            "non_billable_hours", "overtime_hours",
            "submitted_at", "created_at", "updated_at",
        ]


class WeeklyTimesheetDetailSerializer(WeeklyTimesheetSerializer):
    approvals = TimesheetApprovalSerializer(many=True, read_only=True)

    class Meta(WeeklyTimesheetSerializer.Meta):
        fields = WeeklyTimesheetSerializer.Meta.fields + ["approvals"]


class TimesheetSubmitSerializer(serializers.Serializer):
    notes = serializers.CharField(required=False, default="", allow_blank=True)


class TimesheetApprovalActionSerializer(serializers.Serializer):
    action = serializers.ChoiceField(
        choices=[("approved", "Approved"), ("rejected", "Rejected")]
    )
    comment = serializers.CharField(required=False, default="", allow_blank=True)
