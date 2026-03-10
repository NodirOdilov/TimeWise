"""
URL configuration for the clients app.
Clients are managed through the projects app, but this provides
a dedicated endpoint for backward compatibility.
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from apps.projects.views import ClientViewSet

router = DefaultRouter()
router.register(r"", ClientViewSet, basename="client")

urlpatterns = [
    path("", include(router.urls)),
]
