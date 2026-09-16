"""Exceptions raised by the escalation service layer."""


class EscalationError(Exception):
    """Base class for all escalation-domain failures."""


class EscalationNotFoundError(EscalationError):
    pass


class InvalidEscalationRequestError(EscalationError):
    """Malformed request or invalid state transition (e.g. resolving an
    already-resolved escalation, or an unrecognized reason value)."""


class AlreadyAssignedError(EscalationError):
    """Someone else has already claimed this escalation."""
