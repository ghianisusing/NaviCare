"""
Background reminder processing.

There is no Celery/Redis in this project's environment, so this is
implemented as a plain, idempotent function invoked by a management
command (`manage.py process_reminders` — see
notifications/management/commands/process_reminders.py), intended to be
run on a schedule (e.g. cron, or a platform's scheduled-job feature).
In a deployment with Celery available, this function is exactly what a
periodic Celery task's body would call — the idempotency and locking
already implemented here does not change.

Idempotency: a reminder is only ever processed while its status is
still SCHEDULED, re-checked *inside* a row-locked transaction
immediately before creating the notification and flipping it to SENT.
Two overlapping worker runs (or one run happening twice) therefore
never produce a duplicate notification for the same reminder — the
second attempt simply finds nothing left in SCHEDULED state for that row.
"""

from __future__ import annotations

import logging

from django.db import transaction
from django.utils import timezone

from follow_ups.models import FollowUp, Reminder
from follow_ups.services.follow_up_service import get_due_reminders, mark_expired_follow_ups

from . import services

logger = logging.getLogger("notifications")


def _build_message(follow_up: FollowUp) -> tuple[str, str]:
    if follow_up.appointment_id:
        appointment = follow_up.appointment
        title = "Upcoming appointment"
        message = (
            f"Reminder: your appointment with {appointment.provider.display_name} is coming up "
            f"({appointment.start_time:%A, %B %-d at %-I:%M %p})."
        )
        return title, message

    title = "Follow-up reminder"
    message = f"Reminder: {follow_up.title}"
    return title, message


def process_due_reminders(*, as_of=None) -> int:
    """Send (create an in-app notification for) every reminder that's
    currently due. Returns the number actually sent this call."""
    as_of = as_of or timezone.now()
    sent_count = 0

    for reminder in get_due_reminders(as_of=as_of):
        if _process_one_reminder(reminder.id, as_of=as_of):
            sent_count += 1

    return sent_count


def _process_one_reminder(reminder_id: int, *, as_of) -> bool:
    with transaction.atomic():
        try:
            # Row lock + a fresh status re-check is what makes this safe
            # to call from two overlapping worker runs.
            reminder = Reminder.objects.select_for_update().select_related("follow_up", "follow_up__patient").get(
                pk=reminder_id
            )
        except Reminder.DoesNotExist:
            return False

        if reminder.status != Reminder.Status.SCHEDULED:
            return False  # already processed (sent/cancelled) by another run
        if reminder.follow_up.status != FollowUp.Status.PENDING:
            # The follow-up was completed/cancelled after this reminder
            # was scheduled but before the worker got to it.
            reminder.status = Reminder.Status.CANCELLED
            reminder.save(update_fields=["status"])
            return False

        title, message = _build_message(reminder.follow_up)
        notification_type = (
            "appointment_reminder" if reminder.follow_up.appointment_id else "follow_up_reminder"
        )

        services.notify(
            patient=reminder.follow_up.patient,
            notification_type=notification_type,
            title=title,
            message=message,
            related_follow_up=reminder.follow_up,
            related_appointment=reminder.follow_up.appointment,
        )

        reminder.status = Reminder.Status.SENT
        reminder.sent_at = as_of
        reminder.save(update_fields=["status", "sent_at"])

    logger.info(
        "reminder_sent",
        extra={"reminder_id": reminder_id, "follow_up_id": reminder.follow_up_id, "patient_id": reminder.follow_up.patient_id},
    )
    return True


def run_maintenance_cycle() -> dict:
    """Convenience entry point for the scheduled command: process due
    reminders and expire overdue follow-ups in one pass."""
    sent = process_due_reminders()
    expired = mark_expired_follow_ups()
    return {"reminders_sent": sent, "follow_ups_expired": expired}
