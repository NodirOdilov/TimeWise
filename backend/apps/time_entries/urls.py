"""
URL configuration for the time_entries app.
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import TimeEntryViewSet

router = DefaultRouter()
router.register(r"", TimeEntryViewSet, basename="time-entry")

urlpatterns = [
    path("", include(router.urls)),
]
