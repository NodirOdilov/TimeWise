"""
Custom exception handling for the TimeWise API.
"""

import logging

from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import (
    APIException,
    ValidationError,
    NotFound,
    PermissionDenied,
)
from django.core.exceptions import ObjectDoesNotExist
from django.http import Http404

logger = logging.getLogger(__name__)


def custom_exception_handler(exc, context):
    """
    Custom exception handler that provides consistent error response format.
    """
    response = exception_handler(exc, context)

    if response is not None:
        error_payload = {
            "status_code": response.status_code,
            "type": type(exc).__name__,
            "errors": [],
        }

        if isinstance(response.data, dict):
            for field, value in response.data.items():
                if isinstance(value, list):
                    for item in value:
                        error_payload["errors"].append(
                            {
                                "field": field if field != "detail" else None,
                                "message": str(item),
                            }
                        )
                else:
                    error_payload["errors"].append(
                        {
                            "field": field if field != "detail" else None,
                            "message": str(value),
                        }
                    )
        elif isinstance(response.data, list):
            for item in response.data:
                error_payload["errors"].append(
                    {"field": None, "message": str(item)}
                )
        else:
            error_payload["errors"].append(
                {"field": None, "message": str(response.data)}
            )

        response.data = error_payload
    else:
        # Handle unhandled exceptions
        if isinstance(exc, ObjectDoesNotExist):
            error_payload = {
                "status_code": 404,
                "type": "NotFound",
                "errors": [
                    {"field": None, "message": "The requested resource was not found."}
                ],
            }
            response = Response(error_payload, status=status.HTTP_404_NOT_FOUND)
        elif isinstance(exc, Http404):
            error_payload = {
                "status_code": 404,
                "type": "NotFound",
                "errors": [
                    {"field": None, "message": str(exc) or "Not found."}
                ],
            }
            response = Response(error_payload, status=status.HTTP_404_NOT_FOUND)
        else:
            logger.exception("Unhandled exception", exc_info=exc)
            error_payload = {
                "status_code": 500,
                "type": "InternalServerError",
                "errors": [
                    {
                        "field": None,
                        "message": "An unexpected error occurred. Please try again later.",
                    }
                ],
            }
            response = Response(
                error_payload, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    return response


class BusinessLogicError(APIException):
    """Exception for business logic violations."""

    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    default_detail = "A business logic error occurred."
    default_code = "business_logic_error"


class TimerAlreadyRunningError(BusinessLogicError):
    """Raised when a user tries to start a timer while one is already running."""

    default_detail = "A timer is already running. Please stop it before starting a new one."
    default_code = "timer_already_running"


class TimesheetAlreadySubmittedError(BusinessLogicError):
    """Raised when trying to modify an already-submitted timesheet."""

    default_detail = "This timesheet has already been submitted for approval."
    default_code = "timesheet_already_submitted"


class InvoiceAlreadyPaidError(BusinessLogicError):
    """Raised when trying to modify a paid invoice."""

    default_detail = "This invoice has already been paid and cannot be modified."
    default_code = "invoice_already_paid"


class BudgetExceededError(BusinessLogicError):
    """Raised when a project budget would be exceeded."""

    default_detail = "This action would exceed the project budget."
    default_code = "budget_exceeded"


class InsufficientPermissionError(PermissionDenied):
    """Raised when user lacks the required role for an action."""

    default_detail = "You do not have the required role to perform this action."
    default_code = "insufficient_role"
