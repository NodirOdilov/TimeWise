"""
Views for the reports app.
"""

from datetime import datetime, timedelta

from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated

from apps.accounts.permissions import IsManagerOrAbove
from apps.projects.models import Project
from .services import ReportService


class TimeReportView(APIView):
    """
    Generate and retrieve time tracking reports.
    """

    def get(self, request):
        """Generate a time report for the given parameters."""
        period_start = request.query_params.get("start")
        period_end = request.query_params.get("end")
        user_id = request.query_params.get("user_id")
        period = request.query_params.get("period", "custom")

        if not period_start or not period_end:
            today = timezone.now().date()
            if period == "weekly":
                period_start = today - timedelta(days=today.weekday())
                period_end = period_start + timedelta(days=6)
            elif period == "monthly":
                period_start = today.replace(day=1)
                next_month = today.replace(day=28) + timedelta(days=4)
                period_end = next_month - timedelta(days=next_month.day)
            else:
                period_start = today - timedelta(days=30)
                period_end = today
        else:
            try:
                period_start = datetime.strptime(period_start, "%Y-%m-%d").date()
                period_end = datetime.strptime(period_end, "%Y-%m-%d").date()
            except ValueError:
                return Response(
                    {"detail": "Invalid date format. Use YYYY-MM-DD."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        user = None
        if user_id and request.user.is_manager_or_above():
            from django.contrib.auth import get_user_model

            User = get_user_model()
            try:
                user = User.objects.get(
                    id=user_id,
                    organization=request.user.organization,
                )
            except User.DoesNotExist:
                return Response(
                    {"user_id": "User not found."},
                    status=status.HTTP_404_NOT_FOUND,
                )
        elif not request.user.is_manager_or_above():
            user = request.user

        report = ReportService.generate_time_report(
            organization=request.user.organization,
            period_start=period_start,
            period_end=period_end,
            user=user,
        )

        return Response({
            "id": str(report.id),
            "period_start": report.period_start.isoformat(),
            "period_end": report.period_end.isoformat(),
            "total_hours": str(report.total_hours),
            "billable_hours": str(report.billable_hours),
            "non_billable_hours": str(report.non_billable_hours),
            "billable_amount": str(report.billable_amount),
            "cost_amount": str(report.cost_amount),
            "profit_amount": str(report.profit_amount),
            "utilization_percent": str(report.utilization_percent),
            "breakdown_by_project": report.breakdown_by_project,
            "breakdown_by_day": report.breakdown_by_day,
        })


class ProjectReportView(APIView):
    """
    Generate and retrieve project-level reports.
    """

    permission_classes = [IsAuthenticated, IsManagerOrAbove]

    def get(self, request, project_id):
        """Generate a project report."""
        try:
            project = Project.objects.get(
                id=project_id,
                organization=request.user.organization,
            )
        except Project.DoesNotExist:
            return Response(
                {"detail": "Project not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        period_start = request.query_params.get("start")
        period_end = request.query_params.get("end")

        if not period_start or not period_end:
            today = timezone.now().date()
            period_start = project.start_date or (today - timedelta(days=90))
            period_end = today
        else:
            try:
                period_start = datetime.strptime(period_start, "%Y-%m-%d").date()
                period_end = datetime.strptime(period_end, "%Y-%m-%d").date()
            except ValueError:
                return Response(
                    {"detail": "Invalid date format. Use YYYY-MM-DD."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        report = ReportService.generate_project_report(
            project=project,
            period_start=period_start,
            period_end=period_end,
        )

        return Response({
            "id": str(report.id),
            "project": str(project.id),
            "project_name": project.name,
            "period_start": report.period_start.isoformat(),
            "period_end": report.period_end.isoformat(),
            "total_hours": str(report.total_hours),
            "billable_hours": str(report.billable_hours),
            "billable_amount": str(report.billable_amount),
            "cost_amount": str(report.cost_amount),
            "profit_margin_percent": str(report.profit_margin_percent),
            "budget_spent": str(report.budget_spent),
            "budget_total": str(report.budget_total),
            "budget_utilization_percent": str(report.budget_utilization_percent),
            "hours_by_member": report.hours_by_member,
            "hours_by_task": report.hours_by_task,
            "expense_total": str(report.expense_total),
            "invoiced_amount": str(report.invoiced_amount),
            "outstanding_amount": str(report.outstanding_amount),
        })


class TeamReportView(APIView):
    """
    Generate and retrieve team-level reports.
    """

    permission_classes = [IsAuthenticated, IsManagerOrAbove]

    def get(self, request):
        """Generate a team report."""
        team_id = request.query_params.get("team_id")
        period_start = request.query_params.get("start")
        period_end = request.query_params.get("end")

        if not period_start or not period_end:
            today = timezone.now().date()
            period_start = today - timedelta(days=30)
            period_end = today
        else:
            try:
                period_start = datetime.strptime(period_start, "%Y-%m-%d").date()
                period_end = datetime.strptime(period_end, "%Y-%m-%d").date()
            except ValueError:
                return Response(
                    {"detail": "Invalid date format. Use YYYY-MM-DD."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        team = None
        if team_id:
            from apps.accounts.models import Team

            try:
                team = Team.objects.get(
                    id=team_id,
                    organization=request.user.organization,
                )
            except Team.DoesNotExist:
                return Response(
                    {"detail": "Team not found."},
                    status=status.HTTP_404_NOT_FOUND,
                )

        report = ReportService.generate_team_report(
            organization=request.user.organization,
            period_start=period_start,
            period_end=period_end,
            team=team,
        )

        return Response({
            "id": str(report.id),
            "team": str(team.id) if team else None,
            "team_name": team.name if team else "All Teams",
            "period_start": report.period_start.isoformat(),
            "period_end": report.period_end.isoformat(),
            "total_hours": str(report.total_hours),
            "billable_hours": str(report.billable_hours),
            "capacity_hours": str(report.capacity_hours),
            "utilization_percent": str(report.utilization_percent),
            "billable_amount": str(report.billable_amount),
            "cost_amount": str(report.cost_amount),
            "member_breakdown": report.member_breakdown,
            "project_breakdown": report.project_breakdown,
        })
