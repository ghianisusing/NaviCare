"""
Navigator Service — the single entry point the rest of the backend
(specifically `conversations/services/chat_service.py`) calls into.

Responsible for:
  - running the Navigator Agent
  - applying safety validation
  - handling the "route to an agent that doesn't exist yet" case
  - falling back safely on any agent-layer failure
  - basic, privacy-conscious logging

Nothing here touches the database directly except reading/writing
`conversation.summary` — Message persistence stays in chat_service.py,
keeping this module testable without needing a request/response cycle.
"""

from __future__ import annotations

import logging
import time

from agents.core.exceptions import AgentError, InvalidAgentOutputError
from agents.core.llm import LLMMessage, get_llm_provider

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

# Temporary responses for intents that route to agents that don't exist
# yet (Phase 3+). Keyed by target_agent.
AGENT_NOT_READY_RESPONSES = {
    "information": (
        "I can tell this is a general health information question. That "
        "capability is still being prepared, so I can't give a detailed "
        "answer yet — but I can help you figure out where to go for it "
        "in the meantime."
    ),
    "appointment": (
        "Appointment scheduling is still being prepared. I can help you "
        "think through what kind of provider or service you're looking "
        "for in the meantime."
    ),
    "follow_up": (
        "Following up on lab results or prior visits is still being "
        "prepared. For now, your care team or patient portal is the "
        "fastest way to get that information."
    ),
    "triage": (
        "That's still being prepared. Let's talk through what's going "
        "on so I can point you in the right direction."
    ),
}


class NavigatorTurnResult:
    """Everything chat_service.py needs to persist and log one turn."""

    def __init__(self, *, response_text: str, agent_output: AgentOutput, latency_seconds: float, succeeded: bool):
        self.response_text = response_text
        self.agent_output = agent_output
        self.latency_seconds = latency_seconds
        self.succeeded = succeeded


def handle_patient_message(*, conversation, patient_message: str) -> NavigatorTurnResult:
    """Run a full Navigator turn for one patient message.

    Always returns a NavigatorTurnResult with response_text safe to show
    the patient — agent-layer failures are caught here and turned into
    the fallback messages above rather than propagating to the view.
    """
    started_at = time.monotonic()

    try:
        agent_output = run_navigator(conversation=conversation, patient_message=patient_message)
        agent_output = safety.apply_safety_validation(agent_output=agent_output, patient_message=patient_message)
        response_text = _resolve_response_text(agent_output)
        succeeded = True
    except AgentError as exc:
        agent_output = _fallback_output_for(exc, patient_message=patient_message)
        response_text = agent_output.response
        succeeded = False
        logger.warning("Navigator agent failed (%s): %s", type(exc).__name__, exc)

    latency_seconds = time.monotonic() - started_at

    _log_turn(
        conversation=conversation,
        agent_output=agent_output,
        succeeded=succeeded,
        latency_seconds=latency_seconds,
    )

    _maybe_update_summary(conversation=conversation, patient_message=patient_message, response_text=response_text)

    return NavigatorTurnResult(
        response_text=response_text,
        agent_output=agent_output,
        latency_seconds=latency_seconds,
        succeeded=succeeded,
    )


def _resolve_response_text(agent_output: AgentOutput) -> str:
    """Substitutes the "not ready yet" message for routes to agents that
    don't exist yet (Phase 2 has no Information/Appointment/etc. agent
    to actually invoke)."""
    if agent_output.recommended_action == "ROUTE_TO_AGENT" and agent_output.target_agent in AGENT_NOT_READY_RESPONSES:
        return AGENT_NOT_READY_RESPONSES[agent_output.target_agent]
    return agent_output.response


def _fallback_output_for(exc: AgentError, *, patient_message: str) -> AgentOutput:
    # Even on total agent failure, the deterministic safety check still
    # runs — an LLM outage must never suppress an emergency response.
    if safety.matches_emergency_pattern(patient_message):
        return AgentOutput(
            intent="EMERGENCY_CONCERN",
            urgency="emergency",
            needs_clarification=False,
            recommended_action="ESCALATE",
            response=safety.SAFETY_RESPONSE,
            target_agent="escalation",
        )

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
    # Structured, patient-content-free logging per Phase 2 spec: no
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
