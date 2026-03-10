"""
URL configuration for the invoicing app.
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import InvoiceViewSet, PaymentMethodViewSet, TaxRateViewSet

router = DefaultRouter()
router.register(r"invoices", InvoiceViewSet, basename="invoice")
router.register(r"payment-methods", PaymentMethodViewSet, basename="payment-method")
router.register(r"tax-rates", TaxRateViewSet, basename="tax-rate")

urlpatterns = [
    path("", include(router.urls)),
]
