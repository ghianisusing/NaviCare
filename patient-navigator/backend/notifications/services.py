"""
Notification Service — a small channel abstraction so the Follow-Up
Agent and the reminder worker never hardcode "how" a notification is
delivered.

Phase 5 implements only the in-app channel (the Notification model IS
the in-app channel's storage — creating a row is what makes it visible
in the patient's Notifications page). `EmailChannel` is included as a
stub to show the extension point without wiring a real email provider,
per the Phase 5 scope ("Email can be added if practical").
"""

from __future__ import annotations

import abc
import logging

from appointments.models import Appointment
from follow_ups.models import FollowUp
from patients.models import Patient

from .models import Notification

logger = logging.getLogger("notifications")

MAX_MESSAGE_CHARS = 500


class NotificationChannel(abc.ABC):
    @abc.abstractmethod
    def send(
        self,
        *,
        patient: Patient,
        notification_type: str,
        title: str,
        message: str,
        related_follow_up: FollowUp | None,
        related_appointment: Appointment | None,
    ) -> bool:
        """Return True if delivery succeeded (or was recorded)."""
        raise NotImplementedError


class InAppChannel(NotificationChannel):
    """"Sending" an in-app notification just means creating the row —
    the patient sees it next time they open the Notifications page."""

    def send(self, *, patient, notification_type, title, message, related_follow_up, related_appointment) -> bool:
        Notification.objects.create(
            patient=patient,
            type=notification_type,
            title=title[:200],
            message=message[:MAX_MESSAGE_CHARS],
            related_follow_up=related_follow_up,
            related_appointment=related_appointment,
        )
        return True


class EmailChannel(NotificationChannel):
    """Stub — not wired to a real provider in Phase 5. Kept here so the
    extension point is visible: a future implementation would send via
    an email API and return whether delivery succeeded, without any
    caller-side changes."""

    def send(self, *, patient, notification_type, title, message, related_follow_up, related_appointment) -> bool:
        logger.info("EmailChannel is a stub — no email provider configured; skipping send for %s", patient.id)
        return False


def get_active_channels() -> list[NotificationChannel]:
    # Only in-app is active for Phase 5. Adding a channel here (once a
    # real provider is wired up) is the entire integration surface.
    return [InAppChannel()]


def notify(
    *,
    patient: Patient,
    notification_type: str,
    title: str,
    message: str,
    related_follow_up: FollowUp | None = None,
    related_appointment: Appointment | None = None,
) -> None:
    """Dispatch a notification across every active channel.

    A channel failing to send does not raise — see the reminder worker
    (notifications/tasks.py), which needs to keep processing other due
    reminders even if one channel has a transient failure.
    """
    for channel in get_active_channels():
        try:
            channel.send(
                patient=patient,
                notification_type=notification_type,
                title=title,
                message=message,
                related_follow_up=related_follow_up,
                related_appointment=related_appointment,
            )
        except Exception:  # noqa: BLE001
            logger.exception("Notification channel %s failed for patient %s", type(channel).__name__, patient.id)
