"""
Views for the projects app.
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter

from apps.accounts.permissions import IsManagerOrAbove, IsSameOrganization
from .models import Client, Project, ProjectMember, ProjectBudget, Task
from .serializers import (
    ClientSerializer,
    ClientCreateSerializer,
    ProjectSerializer,
    ProjectCreateSerializer,
    ProjectDetailSerializer,
    ProjectMemberSerializer,
    ProjectBudgetSerializer,
    TaskSerializer,
)


class ClientViewSet(viewsets.ModelViewSet):
    """CRUD operations for clients."""

    serializer_class = ClientSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = {"is_active": ["exact"], "currency": ["exact"]}
    search_fields = ["name", "contact_name", "contact_email"]
    ordering_fields = ["name", "created_at"]
    ordering = ["name"]

    def get_queryset(self):
        return Client.objects.filter(
            organization=self.request.user.organization
        )

    def get_serializer_class(self):
        if self.action == "create":
            return ClientCreateSerializer
        return ClientSerializer

    def perform_create(self, serializer):
        serializer.save(organization=self.request.user.organization)


class ProjectViewSet(viewsets.ModelViewSet):
    """CRUD operations for projects."""

    serializer_class = ProjectSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = {
        "status": ["exact", "in"],
        "billing_type": ["exact"],
        "client": ["exact"],
        "is_billable": ["exact"],
    }
    search_fields = ["name", "code", "description"]
    ordering_fields = ["name", "created_at", "start_date", "end_date"]
    ordering = ["name"]

    def get_queryset(self):
        user = self.request.user
        queryset = Project.objects.filter(
            organization=user.organization
        ).select_related("client")

        if not user.is_manager_or_above():
            from django.db.models import Q

            queryset = queryset.filter(
                Q(is_public=True)
                | Q(members__user=user, members__is_active=True)
            ).distinct()

        return queryset

    def get_serializer_class(self):
        if self.action == "create":
            return ProjectCreateSerializer
        if self.action == "retrieve":
            return ProjectDetailSerializer
        return ProjectSerializer

    def perform_create(self, serializer):
        project = serializer.save(organization=self.request.user.organization)
        ProjectMember.objects.create(
            project=project,
            user=self.request.user,
            role=ProjectMember.ProjectRole.PROJECT_MANAGER,
        )

    @action(detail=True, methods=["get"])
    def members(self, request, pk=None):
        """List project members."""
        project = self.get_object()
        members = ProjectMember.objects.filter(
            project=project
        ).select_related("user")
        serializer = ProjectMemberSerializer(members, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def add_member(self, request, pk=None):
        """Add a member to the project."""
        project = self.get_object()
        user_id = request.data.get("user_id")
        role = request.data.get("role", ProjectMember.ProjectRole.MEMBER)

        from django.contrib.auth import get_user_model

        User = get_user_model()

        try:
            user = User.objects.get(
                id=user_id, organization=request.user.organization
            )
        except User.DoesNotExist:
            return Response(
                {"user_id": "User not found in your organization."},
                status=status.HTTP_404_NOT_FOUND,
            )

        member, created = ProjectMember.objects.get_or_create(
            project=project,
            user=user,
            defaults={"role": role},
        )

        if not created:
            member.role = role
            member.is_active = True
            member.save(update_fields=["role", "is_active"])

        return Response(
            ProjectMemberSerializer(member).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"])
    def remove_member(self, request, pk=None):
        """Remove a member from the project."""
        project = self.get_object()
        user_id = request.data.get("user_id")

        try:
            member = ProjectMember.objects.get(
                project=project, user_id=user_id
            )
            member.is_active = False
            member.save(update_fields=["is_active"])
            return Response(status=status.HTTP_204_NO_CONTENT)
        except ProjectMember.DoesNotExist:
            return Response(
                {"user_id": "Member not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

    @action(detail=True, methods=["get", "post"])
    def budgets(self, request, pk=None):
        """List or create project budgets."""
        project = self.get_object()

        if request.method == "GET":
            budgets = ProjectBudget.objects.filter(project=project)
            serializer = ProjectBudgetSerializer(budgets, many=True)
            return Response(serializer.data)

        serializer = ProjectBudgetSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(project=project)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get"])
    def tasks(self, request, pk=None):
        """List project tasks."""
        project = self.get_object()
        task_status = request.query_params.get("status")
        tasks = Task.objects.filter(project=project)
        if task_status:
            tasks = tasks.filter(status=task_status)
        serializer = TaskSerializer(tasks, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["get"])
    def summary(self, request, pk=None):
        """Get project summary with stats."""
        project = self.get_object()
        from apps.time_entries.models import TimeEntry
        from django.db.models import Sum, Count

        entries = TimeEntry.objects.filter(
            project=project, is_running=False
        )

        total_entries = entries.count()
        total_minutes = entries.aggregate(
            total=Sum("duration_minutes")
        )["total"] or 0
        billable_amount = entries.filter(
            is_billable=True
        ).aggregate(total=Sum("billable_amount"))["total"] or 0

        active_tasks = project.tasks.filter(
            status__in=[Task.Status.TODO, Task.Status.IN_PROGRESS]
        ).count()
        completed_tasks = project.tasks.filter(
            status=Task.Status.DONE
        ).count()

        return Response({
            "project_id": str(project.id),
            "total_entries": total_entries,
            "total_hours": round(total_minutes / 60, 2),
            "total_billable_amount": str(billable_amount),
            "estimated_hours": str(project.estimated_hours or 0),
            "budget_utilization": project.budget_utilization_percent,
            "active_tasks": active_tasks,
            "completed_tasks": completed_tasks,
            "member_count": project.members.filter(is_active=True).count(),
        })


class TaskViewSet(viewsets.ModelViewSet):
    """CRUD operations for tasks."""

    serializer_class = TaskSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = {
        "project": ["exact"],
        "status": ["exact", "in"],
        "priority": ["exact"],
        "assignee": ["exact"],
        "is_billable": ["exact"],
    }
    search_fields = ["name", "description"]
    ordering_fields = ["sort_order", "created_at", "due_date", "priority"]
    ordering = ["sort_order", "created_at"]

    def get_queryset(self):
        return Task.objects.filter(
            project__organization=self.request.user.organization
        ).select_related("project", "assignee")

    @action(detail=True, methods=["post"])
    def assign(self, request, pk=None):
        """Assign a user to this task."""
        task = self.get_object()
        user_id = request.data.get("user_id")

        from django.contrib.auth import get_user_model

        User = get_user_model()

        if user_id:
            try:
                user = User.objects.get(
                    id=user_id,
                    organization=request.user.organization,
                )
                task.assignee = user
            except User.DoesNotExist:
                return Response(
                    {"user_id": "User not found."},
                    status=status.HTTP_404_NOT_FOUND,
                )
        else:
            task.assignee = None

        task.save(update_fields=["assignee", "updated_at"])
        return Response(TaskSerializer(task).data)

    @action(detail=True, methods=["post"])
    def update_status(self, request, pk=None):
        """Update task status."""
        task = self.get_object()
        new_status = request.data.get("status")

        if new_status not in dict(Task.Status.choices):
            return Response(
                {"status": f"Invalid status. Choose from: {list(dict(Task.Status.choices).keys())}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        task.status = new_status
        task.save(update_fields=["status", "updated_at"])
        return Response(TaskSerializer(task).data)
