"""
Follow-Up Service (agent layer) — the entry point
`agents/navigator/service.py` calls into when routing to the Follow-Up
Agent. Mirrors agents/appointment/service.py's pattern: read-only and
create actions execute inline; complete/cancel actions are only ever
proposed as a pending AgentAction, requiring the same confirm/decline
endpoints used for appointments (appointments/views.py's
AgentActionConfirmView / AgentActionDeclineView, which dispatch by
tool_name across domains).
"""

from __future__ import annotations

import logging
import time

from agents.core.exceptions import AgentError
from appointments.models import AgentAction
from follow_ups.services import follow_up_service
from follow_ups.services.exceptions import FollowUpError
from tools.exceptions import InvalidToolArgumentsError
from tools.registry import validate_and_prepare

from .agent import run_follow_up_agent
from .schemas import MUTATING_TOOLS_REQUIRING_CONFIRMATION

logger = logging.getLogger("agents.follow_up")

FALLBACK_RESPONSE = "I'm having trouble processing that right now. Please try again shortly."


class FollowUpTurnResult:
    def __init__(
        self,
        *,
        response_text: str,
        follow_up_data: dict | None,
        pending_action: dict | None,
        succeeded: bool,
        latency_seconds: float,
    ):
        self.response_text = response_text
        self.follow_up_data = follow_up_data
        self.pending_action = pending_action
        self.succeeded = succeeded
        self.latency_seconds = latency_seconds


def handle_follow_up_request(*, conversation, patient, patient_message: str) -> FollowUpTurnResult:
    started_at = time.monotonic()

    try:
        result = run_follow_up_agent(conversation=conversation, patient=patient, patient_message=patient_message)
        response_text = result.output.response
        follow_up_data = None
        pending_action = None

        if result.tool_name_executed and result.tool_result is not None:
            follow_up_data = _build_follow_up_data(result.tool_name_executed, result.tool_result)

        if result.output.tool in MUTATING_TOOLS_REQUIRING_CONFIRMATION and not result.output.needs_clarification:
            pending_action, error_text = _propose_action(
                conversation=conversation,
                patient=patient,
                tool_name=result.output.tool,
                raw_arguments=result.output.arguments,
            )
            if error_text:
                response_text = error_text

        succeeded = True
    except AgentError as exc:
        response_text = FALLBACK_RESPONSE
        follow_up_data = None
        pending_action = None
        succeeded = False
        logger.warning("Follow-up agent failed (%s): %s", type(exc).__name__, exc)

    latency_seconds = time.monotonic() - started_at

    logger.info(
        "follow_up_turn",
        extra={
            "conversation_id": conversation.id,
            "agent_type": "follow_up",
            "has_pending_action": pending_action is not None,
            "success": succeeded,
            "latency_ms": round(latency_seconds * 1000),
        },
    )

    return FollowUpTurnResult(
        response_text=response_text,
        follow_up_data=follow_up_data,
        pending_action=pending_action,
        succeeded=succeeded,
        latency_seconds=latency_seconds,
    )


def _propose_action(*, conversation, patient, tool_name: str, raw_arguments: dict):
    try:
        _spec, validated_arguments = validate_and_prepare(tool_name, raw_arguments)
    except InvalidToolArgumentsError as exc:
        return None, f"I wasn't able to prepare that request: {exc}"

    try:
        summary = _validate_and_summarize(tool_name, patient, validated_arguments)
    except FollowUpError as exc:
        return None, str(exc)

    action = AgentAction.objects.create(
        patient=patient,
        conversation=conversation,
        agent="follow_up",
        tool_name=tool_name,
        arguments=validated_arguments,
        status=AgentAction.Status.VALIDATED,
        result_summary=summary,
    )

    return {"id": action.id, "tool_name": tool_name, "summary": summary}, None


def _validate_and_summarize(tool_name: str, patient, arguments: dict) -> str:
    if tool_name == "complete_follow_up":
        follow_up = follow_up_service.get_owned_follow_up(patient=patient, follow_up_id=arguments["follow_up_id"])
        return f"Mark \"{follow_up.title}\" as complete"

    if tool_name == "cancel_follow_up":
        follow_up = follow_up_service.get_owned_follow_up(patient=patient, follow_up_id=arguments["follow_up_id"])
        return f"Cancel follow-up: \"{follow_up.title}\""

    if tool_name == "cancel_reminder":
        reminder = follow_up_service.get_owned_reminder(patient=patient, reminder_id=arguments["reminder_id"])
        return f"Cancel reminder for \"{reminder.follow_up.title}\" ({reminder.scheduled_for:%A, %B %-d · %-I:%M %p})"

    raise FollowUpError("Unsupported action.")


def _build_follow_up_data(tool_name: str, tool_result: dict) -> dict:
    if tool_name == "get_follow_ups":
        return {"type": "follow_up_list", "follow_ups": tool_result.get("follow_ups", [])}
    if tool_name == "get_reminders":
        return {"type": "reminder_list", "reminders": tool_result.get("reminders", [])}
    if tool_name == "create_follow_up":
        return {"type": "follow_up_created", "follow_up": tool_result.get("follow_up")}
    if tool_name == "create_reminder":
        return {"type": "reminder_created", "reminder": tool_result.get("reminder")}
    return {"type": tool_name, **tool_result}
