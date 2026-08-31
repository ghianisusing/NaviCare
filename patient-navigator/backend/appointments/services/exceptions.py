"""Exceptions raised by the appointment service layer.

Kept distinct from Django/DRF exceptions so both the REST views and the
agent tool layer can catch the same errors and translate them into
their own response shape (HTTP status vs. a tool result dict).
"""


class AppointmentError(Exception):
    """Base class for all appointment-domain failures."""


class SlotUnavailableError(AppointmentError):
    """The requested slot is no longer available (already booked, or
    outside any provider availability window)."""


class AppointmentNotFoundError(AppointmentError):
    """No appointment matches the given id (scoped to the patient)."""


class NotOwnerError(AppointmentError):
    """The requesting patient does not own this appointment."""


class InvalidAppointmentRequestError(AppointmentError):
    """The request itself is malformed (bad date range, unknown
    department/provider, etc.) — distinct from an availability conflict."""
