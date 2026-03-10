"""
URL configuration for TimeWise project.
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
    SpectacularRedocView,
)

urlpatterns = [
    path("admin/", admin.site.urls),
    # API routes
    path("api/auth/", include("apps.accounts.urls")),
    path("api/time-entries/", include("apps.time_entries.urls")),
    path("api/projects/", include("apps.projects.urls")),
    path("api/clients/", include("apps.clients.urls")),
    path("api/invoices/", include("apps.invoicing.urls")),
    path("api/expenses/", include("apps.expenses.urls")),
    path("api/reports/", include("apps.reports.urls")),
    path("api/timesheets/", include("apps.timesheets.urls")),
    # API documentation
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

    # Debug toolbar
    try:
        import debug_toolbar
        urlpatterns = [
            path("__debug__/", include(debug_toolbar.urls)),
        ] + urlpatterns
    except ImportError:
        pass

admin.site.site_header = "TimeWise Administration"
admin.site.site_title = "TimeWise Admin"
admin.site.index_title = "Dashboard"
