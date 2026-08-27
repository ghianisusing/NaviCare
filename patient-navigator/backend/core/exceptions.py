"""
Central place for turning any DRF/Django exception into the consistent
error envelope the frontend expects:

    { "error": "<human friendly message>" }

Raw backend errors (stack traces, IntegrityError text, etc.) are never
sent to the client — see settings.LOGGING for where the detail actually
goes instead.
"""

import logging

from django.core.exceptions import PermissionDenied
from django.http import Http404
from rest_framework import exceptions as drf_exceptions
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

logger = logging.getLogger(__name__)

GENERIC_MESSAGE = "Something went wrong. Please try again."


def custom_exception_handler(exc, context):
    """Wrap every handled exception in a single `error` key.

    Validation errors keep DRF's field-level detail (useful for forms);
    everything else collapses to a short, generic message so internal
    details never leak to patients.
    """
    response = drf_exception_handler(exc, context)

    if response is not None:
        if isinstance(exc, drf_exceptions.ValidationError):
            response.data = {"error": "Invalid data submitted.", "details": response.data}
        elif isinstance(exc, (drf_exceptions.NotAuthenticated, drf_exceptions.AuthenticationFailed)):
            response.data = {"error": "Authentication required."}
        elif isinstance(exc, drf_exceptions.PermissionDenied):
            response.data = {"error": "You do not have permission to do that."}
        elif isinstance(exc, drf_exceptions.NotFound):
            response.data = {"error": "Not found."}
        elif isinstance(exc, drf_exceptions.Throttled):
            response.data = {"error": "Too many requests. Please slow down and try again shortly."}
        else:
            response.data = {"error": GENERIC_MESSAGE}
        return response

    # Anything DRF didn't already turn into a Response (raw Django
    # exceptions, unexpected server errors, etc.) — log full detail
    # server-side, return only a generic message to the client.
    if isinstance(exc, Http404):
        return Response({"error": "Not found."}, status=404)
    if isinstance(exc, PermissionDenied):
        return Response({"error": "You do not have permission to do that."}, status=403)

    logger.exception("Unhandled exception in %s", context.get("view"))
    return Response({"error": GENERIC_MESSAGE}, status=500)
