"""Exceptions raised by the follow-up/reminder service layer."""


class FollowUpError(Exception):
    """Base class for all follow-up-domain failures."""


class FollowUpNotFoundError(FollowUpError):
    pass


class ReminderNotFoundError(FollowUpError):
    pass


class NotOwnerError(FollowUpError):
    """The requesting patient does not own this follow-up/reminder."""


class InvalidFollowUpRequestError(FollowUpError):
    """The request itself is malformed (bad date, invalid status transition, etc.)."""
