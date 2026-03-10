"""
Serializers for the projects app.
"""

from rest_framework import serializers

from .models import Client, Project, ProjectMember, ProjectBudget, Task


class ClientSerializer(serializers.ModelSerializer):
    total_outstanding = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True
    )
    project_count = serializers.SerializerMethodField()

    class Meta:
        model = Client
        fields = [
            "id", "organization", "name", "contact_name", "contact_email",
            "contact_phone", "address_line1", "address_line2", "city",
            "state", "postal_code", "country", "tax_id", "currency",
            "payment_terms_days", "notes", "is_active",
            "total_outstanding", "project_count",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "organization", "created_at", "updated_at"]

    def get_project_count(self, obj):
        return obj.projects.filter(
            status__in=[Project.Status.ACTIVE, Project.Status.PLANNING]
        ).count()


class ClientCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Client
        fields = [
            "name", "contact_name", "contact_email", "contact_phone",
            "address_line1", "address_line2", "city", "state",
            "postal_code", "country", "tax_id", "currency",
            "payment_terms_days", "notes",
        ]


class ProjectMemberSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source="user.full_name", read_only=True)
    user_email = serializers.CharField(source="user.email", read_only=True)

    class Meta:
        model = ProjectMember
        fields = [
            "id", "project", "user", "user_name", "user_email",
            "role", "hourly_rate", "is_active", "joined_at",
        ]
        read_only_fields = ["id", "joined_at"]


class ProjectBudgetSerializer(serializers.ModelSerializer):
    spent_amount = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True
    )
    remaining_amount = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True
    )
    utilization_percent = serializers.FloatField(read_only=True)
    is_over_budget = serializers.BooleanField(read_only=True)

    class Meta:
        model = ProjectBudget
        fields = [
            "id", "project", "budget_type", "amount", "currency",
            "hours_budget", "period_start", "period_end",
            "alert_threshold_percent", "is_active",
            "spent_amount", "remaining_amount", "utilization_percent",
            "is_over_budget", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class TaskSerializer(serializers.ModelSerializer):
    assignee_name = serializers.CharField(
        source="assignee.full_name", read_only=True
    )
    total_logged_hours = serializers.FloatField(read_only=True)

    class Meta:
        model = Task
        fields = [
            "id", "project", "name", "description", "status",
            "priority", "assignee", "assignee_name",
            "estimated_hours", "due_date", "is_billable",
            "sort_order", "tags", "total_logged_hours",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class ProjectSerializer(serializers.ModelSerializer):
    client_name = serializers.CharField(source="client.name", read_only=True)
    total_logged_hours = serializers.FloatField(read_only=True)
    total_billable_amount = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True
    )
    budget_utilization_percent = serializers.FloatField(read_only=True)
    member_count = serializers.SerializerMethodField()
    task_count = serializers.SerializerMethodField()

    class Meta:
        model = Project
        fields = [
            "id", "organization", "client", "client_name", "name",
            "code", "description", "color", "status", "billing_type",
            "hourly_rate", "fixed_price", "estimated_hours",
            "start_date", "end_date", "is_billable", "is_public",
            "tags", "total_logged_hours", "total_billable_amount",
            "budget_utilization_percent", "member_count", "task_count",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "organization", "created_at", "updated_at"]

    def get_member_count(self, obj):
        return obj.members.filter(is_active=True).count()

    def get_task_count(self, obj):
        return obj.tasks.count()


class ProjectCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Project
        fields = [
            "client", "name", "code", "description", "color",
            "status", "billing_type", "hourly_rate", "fixed_price",
            "estimated_hours", "start_date", "end_date",
            "is_billable", "is_public", "tags",
        ]

    def validate_code(self, value):
        if value:
            org = self.context["request"].user.organization
            if Project.objects.filter(organization=org, code=value).exists():
                raise serializers.ValidationError(
                    "A project with this code already exists in your organization."
                )
        return value


class ProjectDetailSerializer(ProjectSerializer):
    """Extended project serializer with nested members, tasks, and budgets."""

    members_detail = ProjectMemberSerializer(
        source="members", many=True, read_only=True
    )
    tasks = TaskSerializer(many=True, read_only=True)
    budgets = ProjectBudgetSerializer(many=True, read_only=True)

    class Meta(ProjectSerializer.Meta):
        fields = ProjectSerializer.Meta.fields + [
            "members_detail", "tasks", "budgets",
        ]
