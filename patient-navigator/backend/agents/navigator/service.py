"""
Navigator Service — the single entry point the rest of the backend
(specifically `conversations/services/chat_service.py`) calls into.

This is the orchestrator described in the architecture diagram: it runs
a deterministic emergency pre-check before doing anything else, then —
for non-emergency turns — runs the Navigator Agent to classify intent
and routes GENERAL_HEALTH_INFORMATION to the Information Agent (RAG),
SYMPTOM_CONCERN to the Triage Agent, and APPOINTMENT_REQUEST /
APPOINTMENT_CHANGE to the Appointment Agent (tool-calling; see
agents/appointment/). Routes to agents that still don't exist
(follow_up) get a temporary "being prepared" response.

Nothing here touches the database directly except reading/writing
`conversation.summary` — Message persistence stays in chat_service.py,
keeping this module testable without needing a request/response cycle.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

from agents.core.exceptions import AgentError, InvalidAgentOutputError
from agents.core.llm import LLMMessage, get_llm_provider
from agents.appointment.service import handle_appointment_request
from agents.follow_up.service import handle_follow_up_request
from agents.information.service import handle_information_request
from agents.triage.service import handle_symptom_concern

from . import safety
from .agent import run_navigator
from .prompts import build_summary_prompt
from .schemas import AgentOutput

logger = logging.getLogger("agents.navigator")

# How often (in patient messages) to refresh the rolling summary. Doing
# this every turn would double the LLM calls per message for little
# benefit; every few turns keeps context fresh without the cost.
SUMMARY_UPDATE_INTERVAL = 4

FALLBACK_UNAVAILABLE_RESPONSE = (
    "The assistant is temporarily unavailable. Please try again shortly."
)
FALLBACK_INVALID_OUTPUT_RESPONSE = (
    "The assistant encountered an unexpected problem. Please try again."
)

# Temporary responses for intents that route to agents that still don't
# exist. Information, Triage, Appointment, and Follow-Up are all real
# as of Phase 3/4/5 and are handled by _route below, not this table.
AGENT_NOT_READY_RESPONSES = {
    "escalation": (
        "A human escalation path is still being prepared. If this is "
        "urgent, please contact your healthcare provider directly."
    ),
}


@dataclass
class NavigatorTurnResult:
    """Everything chat_service.py needs to persist and log one turn."""

    response_text: str
    agent_output: AgentOutput
    latency_seconds: float
    succeeded: bool
    sources: list[dict] = field(default_factory=list)
    display_urgency: str = "normal"
    appointment_data: dict | None = None
    pending_action: dict | None = None
    follow_up_data: dict | None = None


def handle_patient_message(*, conversation, patient_message: str) -> NavigatorTurnResult:
    """Run a full Navigator turn for one patient message.

    Always returns a NavigatorTurnResult with response_text safe to show
    the patient — agent-layer failures are caught here and turned into
    the fallback messages above rather than propagating to the view.
    """
    started_at = time.monotonic()

    # Deterministic emergency pre-check, before the Navigator Agent (or
    # any specialist) is even invoked. Per the Phase 3 principle "do not
    # continue asking unnecessary questions once an emergency condition
    # has been identified" — this stops normal navigation outright
    # rather than routing through an LLM call first.
    if safety.matches_emergency_pattern(patient_message):
        agent_output = _emergency_output()
        result = NavigatorTurnResult(
            response_text=agent_output.response,
            agent_output=agent_output,
            latency_seconds=time.monotonic() - started_at,
            succeeded=True,
            sources=[],
            display_urgency="emergency",
        )
        _log_turn(conversation=conversation, agent_output=agent_output, succeeded=True, latency_seconds=result.latency_seconds)
        return result

    try:
        agent_output = run_navigator(conversation=conversation, patient_message=patient_message)
        agent_output = safety.apply_safety_validation(agent_output=agent_output, patient_message=patient_message)
        response_text, sources, display_urgency, appointment_data, pending_action, follow_up_data = _route(
            conversation=conversation, agent_output=agent_output, patient_message=patient_message
        )
        succeeded = True
    except AgentError as exc:
        agent_output = _fallback_output_for(exc, patient_message=patient_message)
        response_text = agent_output.response
        sources = []
        display_urgency = agent_output.urgency if agent_output.urgency != "unknown" else "normal"
        appointment_data = None
        pending_action = None
        follow_up_data = None
        succeeded = False
        logger.warning("Navigator agent failed (%s): %s", type(exc).__name__, exc)

    latency_seconds = time.monotonic() - started_at

    _log_turn(conversation=conversation, agent_output=agent_output, succeeded=succeeded, latency_seconds=latency_seconds)
    _maybe_update_summary(conversation=conversation, patient_message=patient_message, response_text=response_text)

    return NavigatorTurnResult(
        response_text=response_text,
        agent_output=agent_output,
        latency_seconds=latency_seconds,
        succeeded=succeeded,
        sources=sources,
        display_urgency=display_urgency,
        appointment_data=appointment_data,
        pending_action=pending_action,
        follow_up_data=follow_up_data,
    )


def _route(*, conversation, agent_output: AgentOutput, patient_message: str):
    """Resolve the final (response_text, sources, display_urgency,
    appointment_data, pending_action, follow_up_data) for a
    non-emergency Navigator turn, dispatching to a specialist agent
    when the intent/routing calls for one."""
    if agent_output.intent == "GENERAL_HEALTH_INFORMATION":
        info_result = handle_information_request(conversation=conversation, question=patient_message)
        return info_result.response_text, info_result.sources, "normal", None, None, None

    if agent_output.intent == "SYMPTOM_CONCERN":
        triage_result = handle_symptom_concern(conversation=conversation, patient_message=patient_message)
        display_urgency = triage_result.urgency if triage_result.urgency != "unknown" else "normal"
        return triage_result.response_text, [], display_urgency, None, None, None

    if agent_output.intent in ("APPOINTMENT_REQUEST", "APPOINTMENT_CHANGE"):
        appointment_result = handle_appointment_request(
            conversation=conversation, patient=conversation.patient, patient_message=patient_message
        )
        return (
            appointment_result.response_text,
            [],
            "normal",
            appointment_result.appointment_data,
            appointment_result.pending_action,
            None,
        )

    if agent_output.intent == "FOLLOW_UP_REQUEST":
        follow_up_result = handle_follow_up_request(
            conversation=conversation, patient=conversation.patient, patient_message=patient_message
        )
        return (
            follow_up_result.response_text,
            [],
            "normal",
            None,
            follow_up_result.pending_action,
            follow_up_result.follow_up_data,
        )

    if agent_output.recommended_action == "ROUTE_TO_AGENT" and agent_output.target_agent in AGENT_NOT_READY_RESPONSES:
        return AGENT_NOT_READY_RESPONSES[agent_output.target_agent], [], "normal", None, None, None

    return agent_output.response, [], "normal", None, None, None


def _emergency_output() -> AgentOutput:
    return AgentOutput(
        intent="EMERGENCY_CONCERN",
        urgency="emergency",
        needs_clarification=False,
        recommended_action="ESCALATE",
        response=safety.SAFETY_RESPONSE,
        clarifying_question=None,
        target_agent="escalation",
    )


def _fallback_output_for(exc: AgentError, *, patient_message: str) -> AgentOutput:
    # Even on total agent failure, the deterministic safety check still
    # runs — an LLM outage must never suppress an emergency response.
    if safety.matches_emergency_pattern(patient_message):
        return _emergency_output()

    message = (
        FALLBACK_INVALID_OUTPUT_RESPONSE
        if isinstance(exc, InvalidAgentOutputError)
        else FALLBACK_UNAVAILABLE_RESPONSE
    )
    return AgentOutput(
        intent="UNKNOWN",
        urgency="unknown",
        needs_clarification=False,
        recommended_action="RESPOND",
        response=message,
        target_agent=None,
    )


def _log_turn(*, conversation, agent_output: AgentOutput, succeeded: bool, latency_seconds: float) -> None:
    # Structured, patient-content-free logging per Phase 2/3 spec: no
    # message text, no API keys, just enough to observe agent behavior.
    logger.info(
        "navigator_turn",
        extra={
            "conversation_id": conversation.id,
            "agent_type": "navigator",
            "intent": agent_output.intent,
            "target_agent": agent_output.target_agent,
            "action": agent_output.recommended_action,
            "success": succeeded,
            "latency_ms": round(latency_seconds * 1000),
        },
    )


def _maybe_update_summary(*, conversation, patient_message: str, response_text: str) -> None:
    """Best-effort rolling summary refresh — failures here never break
    the main chat flow, they're just skipped and logged."""
    message_count = conversation.messages.count()
    if message_count == 0 or message_count % SUMMARY_UPDATE_INTERVAL != 0:
        return

    try:
        provider = get_llm_provider()
        transcript = "\n".join(
            f"{m.role}: {m.content}" for m in conversation.messages.order_by("created_at")
        )
        result = provider.complete(
            system_prompt=build_summary_prompt(),
            messages=[LLMMessage(role="user", content=transcript)],
            max_tokens=200,
            temperature=0.0,
        )
        conversation.summary = result.text.strip()[:1000]
        conversation.save(update_fields=["summary"])
    except AgentError as exc:
        logger.warning("Summary update skipped after failure: %s", type(exc).__name__)
