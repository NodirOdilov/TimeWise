"""
URL configuration for the reports app.
"""

from django.urls import path

from .views import TimeReportView, ProjectReportView, TeamReportView

urlpatterns = [
    path("time/", TimeReportView.as_view(), name="time-report"),
    path(
        "projects/<uuid:project_id>/",
        ProjectReportView.as_view(),
        name="project-report",
    ),
    path("team/", TeamReportView.as_view(), name="team-report"),
]
