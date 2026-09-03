"""
Follow-Up Service — the single source of truth for follow-up/reminder
business logic. Both the REST API (follow_ups/views.py) and the agent
tools (tools/follow_up_tools.py) call into this module rather than
duplicating logic — same pattern as appointments/services/appointment_service.py.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from django.db import transaction
from django.utils import timezone

from conversations.models import Conversation
from patients.models import Patient

from ..models import FollowUp, Reminder
from .exceptions import (
    FollowUpNotFoundError,
    InvalidFollowUpRequestError,
    NotOwnerError,
    ReminderNotFoundError,
)

MAX_FUTURE_DAYS = 365  # sanity bound against a garbled/hallucinated date far in the future


def _validate_future_datetime(value: datetime, *, field_name: str, allow_none: bool = True) -> None:
    if value is None:
        if allow_none:
            return
        raise InvalidFollowUpRequestError(f"{field_name} is required.")
    if timezone.is_naive(value):
        raise InvalidFollowUpRequestError(f"{field_name} must be timezone-aware.")
    now = timezone.now()
    if value <= now:
        raise InvalidFollowUpRequestError(f"{field_name} must be in the future.")
    if value > now + timedelta(days=MAX_FUTURE_DAYS):
        raise InvalidFollowUpRequestError(f"{field_name} is too far in the future.")


# ---------------------------------------------------------------------------
# Follow-ups
# ---------------------------------------------------------------------------


def create_follow_up(
    *,
    patient: Patient,
    title: str,
    description: str = "",
    due_at: datetime | None = None,
    priority: str = FollowUp.Priority.NORMAL,
    conversation: Conversation | None = None,
    appointment=None,
) -> FollowUp:
    title = title.strip()
    if not title:
        raise InvalidFollowUpRequestError("title is required.")
    if priority not in FollowUp.Priority.values:
        raise InvalidFollowUpRequestError(f"Invalid priority: {priority!r}")

    _validate_future_datetime(due_at, field_name="due_at", allow_none=True)

    return FollowUp.objects.create(
        patient=patient,
        conversation=conversation,
        appointment=appointment,
        title=title,
        description=description,
        due_at=due_at,
        priority=priority,
    )


def get_patient_follow_ups(*, patient: Patient, status: str | None = None) -> list[FollowUp]:
    queryset = FollowUp.objects.filter(patient=patient).select_related("appointment", "appointment__provider")
    if status:
        queryset = queryset.filter(status=status)
    return list(queryset)


def _get_owned_follow_up(*, patient: Patient, follow_up_id: int) -> FollowUp:
    try:
        follow_up = FollowUp.objects.get(pk=follow_up_id)
    except FollowUp.DoesNotExist as exc:
        raise FollowUpNotFoundError("No follow-up found with that id.") from exc
    if follow_up.patient_id != patient.id:
        raise NotOwnerError("This follow-up does not belong to the requesting patient.")
    return follow_up


get_owned_follow_up = _get_owned_follow_up


@transaction.atomic
def complete_follow_up(*, patient: Patient, follow_up_id: int) -> FollowUp:
    follow_up = _get_owned_follow_up(patient=patient, follow_up_id=follow_up_id)
    if follow_up.status != FollowUp.Status.PENDING:
        raise InvalidFollowUpRequestError("Only a pending follow-up can be completed.")

    follow_up.status = FollowUp.Status.COMPLETED
    follow_up.completed_at = timezone.now()
    follow_up.save(update_fields=["status", "completed_at", "updated_at"])

    # Completing the task makes any pending reminder about it moot.
    follow_up.reminders.filter(status=Reminder.Status.SCHEDULED).update(status=Reminder.Status.CANCELLED)
    return follow_up


@transaction.atomic
def cancel_follow_up(*, patient: Patient, follow_up_id: int) -> FollowUp:
    follow_up = _get_owned_follow_up(patient=patient, follow_up_id=follow_up_id)
    if follow_up.status != FollowUp.Status.PENDING:
        raise InvalidFollowUpRequestError("Only a pending follow-up can be cancelled.")

    follow_up.status = FollowUp.Status.CANCELLED
    follow_up.save(update_fields=["status", "updated_at"])

    follow_up.reminders.filter(status=Reminder.Status.SCHEDULED).update(status=Reminder.Status.CANCELLED)
    return follow_up


def mark_expired_follow_ups(*, as_of: datetime | None = None) -> int:
    """Mark pending follow-ups whose due_at has passed as expired.
    Purely administrative — never implies a clinical judgment (see the
    Phase 5 boundary: "do not automatically mark a patient as having
    failed to follow medical instructions")."""
    as_of = as_of or timezone.now()
    updated = FollowUp.objects.filter(status=FollowUp.Status.PENDING, due_at__isnull=False, due_at__lt=as_of).update(
        status=FollowUp.Status.EXPIRED
    )
    return updated


# ---------------------------------------------------------------------------
# Reminders
# ---------------------------------------------------------------------------


@transaction.atomic
def create_reminder(*, patient: Patient, follow_up_id: int, scheduled_for: datetime) -> Reminder:
    follow_up = _get_owned_follow_up(patient=patient, follow_up_id=follow_up_id)
    if follow_up.status != FollowUp.Status.PENDING:
        raise InvalidFollowUpRequestError("Cannot schedule a reminder for a follow-up that isn't pending.")

    _validate_future_datetime(scheduled_for, field_name="scheduled_for", allow_none=False)

    return Reminder.objects.create(follow_up=follow_up, scheduled_for=scheduled_for)


def get_patient_reminders(*, patient: Patient, status: str | None = None) -> list[Reminder]:
    queryset = Reminder.objects.filter(follow_up__patient=patient).select_related("follow_up")
    if status:
        queryset = queryset.filter(status=status)
    return list(queryset)


def _get_owned_reminder(*, patient: Patient, reminder_id: int) -> Reminder:
    try:
        reminder = Reminder.objects.select_related("follow_up").get(pk=reminder_id)
    except Reminder.DoesNotExist as exc:
        raise ReminderNotFoundError("No reminder found with that id.") from exc
    if reminder.follow_up.patient_id != patient.id:
        raise NotOwnerError("This reminder does not belong to the requesting patient.")
    return reminder


get_owned_reminder = _get_owned_reminder


@transaction.atomic
def cancel_reminder(*, patient: Patient, reminder_id: int) -> Reminder:
    reminder = _get_owned_reminder(patient=patient, reminder_id=reminder_id)
    if reminder.status != Reminder.Status.SCHEDULED:
        raise InvalidFollowUpRequestError("Only a scheduled reminder can be cancelled.")

    reminder.status = Reminder.Status.CANCELLED
    reminder.save(update_fields=["status"])
    return reminder


@transaction.atomic
def reschedule_reminder(*, patient: Patient, reminder_id: int, new_scheduled_for: datetime) -> Reminder:
    reminder = _get_owned_reminder(patient=patient, reminder_id=reminder_id)
    if reminder.status != Reminder.Status.SCHEDULED:
        raise InvalidFollowUpRequestError("Only a scheduled reminder can be rescheduled.")

    _validate_future_datetime(new_scheduled_for, field_name="scheduled_for", allow_none=False)

    reminder.scheduled_for = new_scheduled_for
    reminder.save(update_fields=["scheduled_for"])
    return reminder


def get_due_reminders(*, as_of: datetime | None = None):
    """Reminders ready for the background worker to send: still
    scheduled, due, and whose follow-up is still pending (a follow-up
    that was completed/cancelled already cancelled its own reminders —
    see complete_follow_up/cancel_follow_up — but this filter is a
    second, independent guarantee against ever sending for a
    non-pending follow-up)."""
    as_of = as_of or timezone.now()
    return Reminder.objects.filter(
        status=Reminder.Status.SCHEDULED, scheduled_for__lte=as_of, follow_up__status=FollowUp.Status.PENDING
    ).select_related("follow_up", "follow_up__patient")
