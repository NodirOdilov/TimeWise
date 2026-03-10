"""
URL configuration for the timesheets app.
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import WeeklyTimesheetViewSet

router = DefaultRouter()
router.register(r"", WeeklyTimesheetViewSet, basename="timesheet")

urlpatterns = [
    path("", include(router.urls)),
]
