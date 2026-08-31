"""
Appointment Service (agent layer) — the entry point
`agents/navigator/service.py` calls into when routing to the
Appointment Agent.

Responsible for:
  - running the (bounded, 2-hop-max) Appointment Agent
  - turning a *read-only* tool result into frontend-renderable data
  - turning a *mutating* tool proposal into a pending AgentAction —
    never executing it directly (see appointments/services/appointment_service.py
    and tools/registry.py for where execution actually happens, driven
    by the confirm endpoint in appointments/views.py)
  - safe fallback on any agent-layer failure
"""

from __future__ import annotations

import logging
import time

from agents.core.exceptions import AgentError
from appointments.models import AgentAction, Provider
from appointments.services.appointment_service import get_owned_appointment
from appointments.services.exceptions import AppointmentError
from tools.exceptions import InvalidToolArgumentsError
from tools.registry import validate_and_prepare

from .agent import MUTATING_TOOLS, run_appointment_agent

logger = logging.getLogger("agents.appointment")

FALLBACK_RESPONSE = "I'm having trouble processing that right now. Please try again shortly."


class AppointmentTurnResult:
    def __init__(
        self,
        *,
        response_text: str,
        appointment_data: dict | None,
        pending_action: dict | None,
        succeeded: bool,
        latency_seconds: float,
    ):
        self.response_text = response_text
        self.appointment_data = appointment_data
        self.pending_action = pending_action
        self.succeeded = succeeded
        self.latency_seconds = latency_seconds


def handle_appointment_request(*, conversation, patient, patient_message: str) -> AppointmentTurnResult:
    started_at = time.monotonic()

    try:
        result = run_appointment_agent(conversation=conversation, patient=patient, patient_message=patient_message)
        response_text = result.output.response
        appointment_data = None
        pending_action = None

        if result.tool_name_executed and result.tool_result is not None:
            appointment_data = _build_appointment_data(result.tool_name_executed, result.tool_result)

        if result.output.tool in MUTATING_TOOLS and not result.output.needs_clarification:
            pending_action, error_text = _propose_action(
                conversation=conversation,
                patient=patient,
                tool_name=result.output.tool,
                raw_arguments=result.output.arguments,
                agent_response_text=response_text,
            )
            if error_text:
                response_text = error_text

        succeeded = True
    except AgentError as exc:
        response_text = FALLBACK_RESPONSE
        appointment_data = None
        pending_action = None
        succeeded = False
        logger.warning("Appointment agent failed (%s): %s", type(exc).__name__, exc)

    latency_seconds = time.monotonic() - started_at

    logger.info(
        "appointment_turn",
        extra={
            "conversation_id": conversation.id,
            "agent_type": "appointment",
            "has_pending_action": pending_action is not None,
            "success": succeeded,
            "latency_ms": round(latency_seconds * 1000),
        },
    )

    return AppointmentTurnResult(
        response_text=response_text,
        appointment_data=appointment_data,
        pending_action=pending_action,
        succeeded=succeeded,
        latency_seconds=latency_seconds,
    )


def _propose_action(*, conversation, patient, tool_name: str, raw_arguments: dict, agent_response_text: str):
    """Validate a mutating tool request and record it as a pending
    AgentAction — never executes it. Returns (pending_action_dict,
    error_text_or_None).

    This only performs a lightweight existence/ownership pre-check, not
    a full availability re-check — that happens for real, inside a
    transaction, when the patient confirms (see
    appointments/views.py:AgentActionConfirmView and
    appointment_service.book_appointment/cancel_appointment/
    reschedule_appointment). A slot that was available at proposal time
    but taken by the time of confirmation is handled there, not here.
    """
    try:
        _spec, validated_arguments = validate_and_prepare(tool_name, raw_arguments)
    except InvalidToolArgumentsError as exc:
        return None, f"I wasn't able to prepare that request: {exc}"

    try:
        summary = _validate_and_summarize(tool_name, patient, validated_arguments)
    except AppointmentError as exc:
        return None, str(exc)

    action = AgentAction.objects.create(
        patient=patient,
        conversation=conversation,
        agent="appointment",
        tool_name=tool_name,
        arguments=_json_safe(validated_arguments),
        status=AgentAction.Status.VALIDATED,
        result_summary=summary,
    )

    return {"id": action.id, "tool_name": tool_name, "summary": summary}, None


def _validate_and_summarize(tool_name: str, patient, arguments: dict) -> str:
    """Existence/ownership pre-check + a human-readable summary for the
    confirmation card. Raises AppointmentError subclasses on failure."""
    if tool_name == "book_appointment":
        try:
            provider = Provider.objects.select_related("department").get(pk=arguments["provider_id"], active=True)
        except Provider.DoesNotExist as exc:
            raise AppointmentError("I couldn't find that provider anymore. Let's search again.") from exc
        start = arguments["start_time"]
        return f"Book with {provider.display_name} ({provider.department.name}) at {start:%A, %B %-d, %Y · %-I:%M %p}"

    if tool_name == "cancel_appointment":
        appointment = get_owned_appointment(patient=patient, appointment_id=arguments["appointment_id"])
        return (
            f"Cancel your appointment with {appointment.provider.display_name} "
            f"on {appointment.start_time:%A, %B %-d, %Y · %-I:%M %p}"
        )

    if tool_name == "reschedule_appointment":
        appointment = get_owned_appointment(patient=patient, appointment_id=arguments["appointment_id"])
        new_start = arguments["new_start_time"]
        return (
            f"Move your appointment with {appointment.provider.display_name} "
            f"to {new_start:%A, %B %-d, %Y · %-I:%M %p}"
        )

    raise AppointmentError("Unsupported action.")


def _json_safe(arguments: dict) -> dict:
    safe = {}
    for key, value in arguments.items():
        safe[key] = value.isoformat() if hasattr(value, "isoformat") else value
    return safe


def _build_appointment_data(tool_name: str, tool_result: dict) -> dict:
    if tool_name == "find_available_slots":
        return {"type": "slot_options", "slots": tool_result.get("slots", [])}
    if tool_name == "get_patient_appointments":
        return {"type": "appointment_list", "appointments": tool_result.get("appointments", [])}
    if tool_name == "search_departments":
        return {"type": "department_list", "departments": tool_result.get("departments", [])}
    if tool_name == "search_providers":
        return {"type": "provider_list", "providers": tool_result.get("providers", [])}
    return {"type": tool_name, **tool_result}
