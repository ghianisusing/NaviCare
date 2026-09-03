"""
Follow-up/reminder tool definitions — registered with the same central
tool registry used by appointments (tools/registry.py). Every handler
takes `patient` plus already-validated arguments and returns a plain,
JSON-serializable dict, same convention as tools/appointment_tools.py.
"""

from __future__ import annotations

from follow_ups.services import follow_up_service
from follow_ups.services.exceptions import FollowUpError, NotOwnerError

from .exceptions import ToolAuthorizationError, ToolError
from .registry import register_tool
from .schemas import ToolField, ToolSpec


def _serialize_follow_up(follow_up) -> dict:
    return {
        "id": follow_up.id,
        "title": follow_up.title,
        "description": follow_up.description,
        "due_at": follow_up.due_at.isoformat() if follow_up.due_at else None,
        "status": follow_up.status,
        "priority": follow_up.priority,
        "appointment_id": follow_up.appointment_id,
    }


def _serialize_reminder(reminder) -> dict:
    return {
        "id": reminder.id,
        "follow_up_id": reminder.follow_up_id,
        "follow_up_title": reminder.follow_up.title,
        "scheduled_for": reminder.scheduled_for.isoformat(),
        "status": reminder.status,
    }


def _handle_create_follow_up(patient, *, title: str, description: str = "", due_at=None, priority: str = "normal") -> dict:
    try:
        follow_up = follow_up_service.create_follow_up(
            patient=patient, title=title, description=description, due_at=due_at, priority=priority
        )
    except FollowUpError as exc:
        raise ToolError(str(exc)) from exc
    return {"follow_up": _serialize_follow_up(follow_up)}


def _handle_get_follow_ups(patient, *, status: str = "") -> dict:
    follow_ups = follow_up_service.get_patient_follow_ups(patient=patient, status=status or None)
    return {"follow_ups": [_serialize_follow_up(f) for f in follow_ups]}


def _handle_complete_follow_up(patient, *, follow_up_id: int) -> dict:
    try:
        follow_up = follow_up_service.complete_follow_up(patient=patient, follow_up_id=follow_up_id)
    except NotOwnerError as exc:
        raise ToolAuthorizationError(str(exc)) from exc
    except FollowUpError as exc:
        raise ToolError(str(exc)) from exc
    return {"follow_up": _serialize_follow_up(follow_up)}


def _handle_cancel_follow_up(patient, *, follow_up_id: int) -> dict:
    try:
        follow_up = follow_up_service.cancel_follow_up(patient=patient, follow_up_id=follow_up_id)
    except NotOwnerError as exc:
        raise ToolAuthorizationError(str(exc)) from exc
    except FollowUpError as exc:
        raise ToolError(str(exc)) from exc
    return {"follow_up": _serialize_follow_up(follow_up)}


def _handle_create_reminder(patient, *, follow_up_id: int, scheduled_for) -> dict:
    try:
        reminder = follow_up_service.create_reminder(patient=patient, follow_up_id=follow_up_id, scheduled_for=scheduled_for)
    except NotOwnerError as exc:
        raise ToolAuthorizationError(str(exc)) from exc
    except FollowUpError as exc:
        raise ToolError(str(exc)) from exc
    return {"reminder": _serialize_reminder(reminder)}


def _handle_get_reminders(patient, *, status: str = "") -> dict:
    reminders = follow_up_service.get_patient_reminders(patient=patient, status=status or None)
    return {"reminders": [_serialize_reminder(r) for r in reminders]}


def _handle_cancel_reminder(patient, *, reminder_id: int) -> dict:
    try:
        reminder = follow_up_service.cancel_reminder(patient=patient, reminder_id=reminder_id)
    except NotOwnerError as exc:
        raise ToolAuthorizationError(str(exc)) from exc
    except FollowUpError as exc:
        raise ToolError(str(exc)) from exc
    return {"reminder": _serialize_reminder(reminder)}


register_tool(
    ToolSpec(
        name="create_follow_up",
        description="Create a navigation follow-up task for the requesting patient.",
        fields=[
            ToolField("title", "str"),
            ToolField("description", "str", required=False),
            ToolField("due_at", "datetime", required=False),
            ToolField("priority", "str", required=False, allowed_values=("normal", "high")),
        ],
        requires_confirmation=False,
        handler=_handle_create_follow_up,
    )
)

register_tool(
    ToolSpec(
        name="get_follow_ups",
        description="List the requesting patient's own follow-up tasks, optionally filtered by status.",
        fields=[
            ToolField(
                "status", "str", required=False, allowed_values=("pending", "completed", "cancelled", "expired")
            )
        ],
        requires_confirmation=False,
        handler=_handle_get_follow_ups,
    )
)

register_tool(
    ToolSpec(
        name="complete_follow_up",
        description="Mark one of the requesting patient's own follow-ups as completed.",
        fields=[ToolField("follow_up_id", "int")],
        requires_confirmation=True,
        handler=_handle_complete_follow_up,
    )
)

register_tool(
    ToolSpec(
        name="cancel_follow_up",
        description="Cancel one of the requesting patient's own pending follow-ups.",
        fields=[ToolField("follow_up_id", "int")],
        requires_confirmation=True,
        handler=_handle_cancel_follow_up,
    )
)

register_tool(
    ToolSpec(
        name="create_reminder",
        description="Schedule a reminder for one of the requesting patient's own pending follow-ups.",
        fields=[ToolField("follow_up_id", "int"), ToolField("scheduled_for", "datetime")],
        requires_confirmation=False,
        handler=_handle_create_reminder,
    )
)

register_tool(
    ToolSpec(
        name="get_reminders",
        description="List the requesting patient's own reminders, optionally filtered by status.",
        fields=[ToolField("status", "str", required=False, allowed_values=("scheduled", "sent", "cancelled", "failed"))],
        requires_confirmation=False,
        handler=_handle_get_reminders,
    )
)

register_tool(
    ToolSpec(
        name="cancel_reminder",
        description="Cancel one of the requesting patient's own scheduled reminders.",
        fields=[ToolField("reminder_id", "int")],
        requires_confirmation=True,
        handler=_handle_cancel_reminder,
    )
)
