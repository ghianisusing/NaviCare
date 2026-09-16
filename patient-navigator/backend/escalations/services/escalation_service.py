"""
Escalation Service — the single source of truth for escalation business
logic. Both the REST API (escalations/views.py) and the Escalation
Agent (agents/escalation/service.py) call into this module.

Per Phase 6 point 6: an LLM can *recommend* escalation, but this module
is the actual authorization boundary — every reason is validated
against the `Escalation.Reason` choices before a row is created, and
duplicate open escalations for the same conversation are collapsed
rather than piling up.
"""

from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from appointments.models import AgentAction, Appointment
from conversations.models import Conversation, Message
from follow_ups.models import FollowUp
from notifications import services as notification_services
from patients.models import Patient

from ..models import Escalation, EscalationEvent
from .exceptions import AlreadyAssignedError, EscalationNotFoundError, InvalidEscalationRequestError

OPEN_STATUSES = (Escalation.Status.PENDING, Escalation.Status.ASSIGNED, Escalation.Status.IN_PROGRESS)

MAX_SUMMARY_ITEMS = 5


def build_internal_summary(*, conversation: Conversation, patient: Patient) -> dict:
    """Deterministically build the structured, staff-facing summary —
    never an LLM-generated diagnosis. Reuses the conversation's own
    rolling summary (agents/navigator/service.py) plus a lookup of
    genuinely relevant records, not the raw conversation transcript."""
    relevant_appointments = list(
        Appointment.objects.filter(patient=patient, status=Appointment.Status.SCHEDULED)
        .select_related("provider", "provider__department")
        .order_by("start_time")[:MAX_SUMMARY_ITEMS]
    )
    relevant_follow_ups = list(
        FollowUp.objects.filter(patient=patient, status=FollowUp.Status.PENDING).order_by("due_at")[:MAX_SUMMARY_ITEMS]
    )
    recent_actions = list(
        AgentAction.objects.filter(conversation=conversation).order_by("-created_at")[:MAX_SUMMARY_ITEMS]
    )

    return {
        "summary": conversation.summary or "No conversation summary available yet.",
        "relevant_appointments": [
            {
                "id": a.id,
                "provider_name": a.provider.display_name,
                "department_name": a.provider.department.name,
                "start_time": a.start_time.isoformat(),
            }
            for a in relevant_appointments
        ],
        "relevant_follow_ups": [
            {"id": f.id, "title": f.title, "due_at": f.due_at.isoformat() if f.due_at else None}
            for f in relevant_follow_ups
        ],
        "agent_actions": [{"tool_name": a.tool_name, "status": a.status} for a in recent_actions],
    }


@transaction.atomic
def create_escalation(
    *, patient: Patient, conversation: Conversation, reason: str, priority: str = Escalation.Priority.NORMAL
) -> Escalation:
    if reason not in Escalation.Reason.values:
        raise InvalidEscalationRequestError(f"Invalid escalation reason: {reason!r}")
    if priority not in Escalation.Priority.values:
        raise InvalidEscalationRequestError(f"Invalid escalation priority: {priority!r}")

    existing = Escalation.objects.filter(conversation=conversation, status__in=OPEN_STATUSES).first()
    if existing is not None:
        return existing  # idempotent — never stack duplicate open escalations for one conversation

    escalation = Escalation.objects.create(
        patient=patient,
        conversation=conversation,
        reason=reason,
        priority=priority,
        summary=build_internal_summary(conversation=conversation, patient=patient),
    )
    EscalationEvent.objects.create(escalation=escalation, actor=None, action=EscalationEvent.Action.CREATED)
    return escalation


def get_staff_queue(*, status: str | None = None, assigned_to_id: int | None = None):
    queryset = Escalation.objects.select_related("patient", "conversation", "assigned_to")
    if status:
        queryset = queryset.filter(status=status)
    if assigned_to_id:
        queryset = queryset.filter(assigned_to_id=assigned_to_id)
    return queryset


def get_patient_escalations(*, patient: Patient):
    return Escalation.objects.filter(patient=patient)


def _get_escalation(escalation_id: int) -> Escalation:
    try:
        return Escalation.objects.select_related("patient", "conversation").get(pk=escalation_id)
    except Escalation.DoesNotExist as exc:
        raise EscalationNotFoundError("No escalation found with that id.") from exc


@transaction.atomic
def assign_escalation(*, staff_user, escalation_id: int) -> Escalation:
    escalation = _get_escalation(escalation_id)

    if escalation.status not in (Escalation.Status.PENDING, Escalation.Status.ASSIGNED):
        raise InvalidEscalationRequestError("This escalation is no longer open for assignment.")
    if escalation.assigned_to_id is not None and escalation.assigned_to_id != staff_user.id:
        raise AlreadyAssignedError("This escalation has already been claimed by another staff member.")

    escalation.assigned_to = staff_user
    escalation.status = Escalation.Status.ASSIGNED
    escalation.save(update_fields=["assigned_to", "status", "updated_at"])
    EscalationEvent.objects.create(escalation=escalation, actor=staff_user, action=EscalationEvent.Action.ASSIGNED)
    return escalation


@transaction.atomic
def send_staff_response(*, staff_user, escalation_id: int, content: str) -> Message:
    escalation = _get_escalation(escalation_id)

    if escalation.assigned_to_id not in (staff_user.id, None) and not staff_user.is_superuser:
        raise InvalidEscalationRequestError("This escalation is assigned to a different staff member.")
    if escalation.status not in (Escalation.Status.PENDING, Escalation.Status.ASSIGNED, Escalation.Status.IN_PROGRESS):
        raise InvalidEscalationRequestError("This escalation is no longer active.")

    content = content.strip()
    if not content:
        raise InvalidEscalationRequestError("Response content cannot be empty.")

    message = Message.objects.create(
        conversation=escalation.conversation, role=Message.Role.STAFF, content=content, sender_staff=staff_user
    )

    if escalation.assigned_to_id is None:
        escalation.assigned_to = staff_user
    escalation.status = Escalation.Status.IN_PROGRESS
    escalation.save(update_fields=["assigned_to", "status", "updated_at"])

    EscalationEvent.objects.create(
        escalation=escalation, actor=staff_user, action=EscalationEvent.Action.STAFF_RESPONSE_SENT
    )

    notification_services.notify(
        patient=escalation.patient,
        notification_type="system",
        title="New message from Care Support",
        message="A care coordinator has responded in your conversation.",
    )
    return message


@transaction.atomic
def resolve_escalation(*, staff_user, escalation_id: int) -> Escalation:
    escalation = _get_escalation(escalation_id)

    if escalation.status in (Escalation.Status.RESOLVED, Escalation.Status.CANCELLED):
        raise InvalidEscalationRequestError("This escalation is already closed.")
    if escalation.assigned_to_id not in (staff_user.id, None) and not staff_user.is_superuser:
        raise InvalidEscalationRequestError("This escalation is assigned to a different staff member.")

    escalation.status = Escalation.Status.RESOLVED
    escalation.resolved_at = timezone.now()
    escalation.save(update_fields=["status", "resolved_at", "updated_at"])
    EscalationEvent.objects.create(escalation=escalation, actor=staff_user, action=EscalationEvent.Action.RESOLVED)
    return escalation


@transaction.atomic
def cancel_escalation(*, escalation_id: int, actor=None) -> Escalation:
    escalation = _get_escalation(escalation_id)
    if escalation.status in (Escalation.Status.RESOLVED, Escalation.Status.CANCELLED):
        raise InvalidEscalationRequestError("This escalation is already closed.")

    escalation.status = Escalation.Status.CANCELLED
    escalation.save(update_fields=["status", "updated_at"])
    EscalationEvent.objects.create(escalation=escalation, actor=actor, action=EscalationEvent.Action.CANCELLED)
    return escalation
