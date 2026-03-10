"""
URL configuration for the projects app.
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import ClientViewSet, ProjectViewSet, TaskViewSet

router = DefaultRouter()
router.register(r"clients", ClientViewSet, basename="client")
router.register(r"projects", ProjectViewSet, basename="project")
router.register(r"tasks", TaskViewSet, basename="task")

urlpatterns = [
    path("", include(router.urls)),
]
