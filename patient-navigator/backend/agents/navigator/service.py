"""
Navigator Service — the single entry point the rest of the backend
(specifically `conversations/services/chat_service.py`) calls into.

This is the orchestrator described in the architecture diagram: it runs
a deterministic emergency pre-check before doing anything else, then —
for non-emergency turns — runs the Navigator Agent to classify intent
and routes to the appropriate specialist agent (Information, Triage,
Appointment, Follow-Up, or — as of Phase 6 — Escalation for explicit
human requests, out-of-scope requests, or repeated agent failures).

As of Phase 6, every turn is wrapped in an observability.Tracer, giving
each turn a request_id that correlates its AgentTrace/AgentTraceStep
rows — see observability/tracing.py. Nothing here touches the database
directly beyond that, `conversation.summary`, and
`conversation.consecutive_agent_failures` — Message persistence stays
in chat_service.py, keeping this module testable without needing a
request/response cycle.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

from django.conf import settings

from agents.core.exceptions import AgentError, InvalidAgentOutputError
from agents.core.llm import LLMMessage, get_llm_provider
from agents.appointment.service import handle_appointment_request
from agents.escalation import service as escalation_agent_service
from agents.escalation.prompts import build_escalation_response
from agents.follow_up.service import handle_follow_up_request
from agents.information.service import handle_information_request
from agents.triage.service import handle_symptom_concern
from escalations.models import Escalation
from escalations.services import escalation_service
from escalations.services.exceptions import EscalationError
from observability.errors import classify_exception
from observability.tracing import Tracer

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

# Everything below is real as of Phase 3/4/5/6 and handled by _route;
# this table exists purely so a *future*, genuinely unimplemented
# target_agent value degrades gracefully instead of crashing.
AGENT_NOT_READY_RESPONSES: dict[str, str] = {}


@dataclass
class RouteResult:
    response_text: str
    sources: list[dict] = field(default_factory=list)
    display_urgency: str = "normal"
    appointment_data: dict | None = None
    pending_action: dict | None = None
    follow_up_data: dict | None = None
    escalation_id: int | None = None
    final_agent: str = "navigator"


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
    escalation_id: int | None = None
    request_id: str | None = None
    final_agent: str = "navigator"


def handle_patient_message(*, conversation, patient_message: str) -> NavigatorTurnResult:
    """Run a full Navigator turn for one patient message.

    Always returns a NavigatorTurnResult with response_text safe to show
    the patient — agent-layer failures are caught here and turned into
    the fallback messages above rather than propagating to the view.
    """
    started_at = time.monotonic()
    patient = conversation.patient
    tracer = Tracer(conversation=conversation, patient=patient)

    # Deterministic emergency pre-check, before the Navigator Agent (or
    # any specialist) is even invoked. Per the Phase 3 principle "do not
    # continue asking unnecessary questions once an emergency condition
    # has been identified" — this stops normal navigation outright
    # rather than routing through an LLM call first.
    with tracer.step("safety", "emergency_pre_check") as step:
        is_emergency = safety.matches_emergency_pattern(patient_message)
        step.metadata["matched"] = is_emergency

    if is_emergency:
        agent_output = _emergency_output()
        latency_seconds = time.monotonic() - started_at
        tracer.finish(status="completed", final_agent="emergency")
        _log_turn(conversation=conversation, agent_output=agent_output, succeeded=True, latency_seconds=latency_seconds)
        return NavigatorTurnResult(
            response_text=agent_output.response,
            agent_output=agent_output,
            latency_seconds=latency_seconds,
            succeeded=True,
            sources=[],
            display_urgency="emergency",
            request_id=str(tracer.request_id),
            final_agent="emergency",
        )

    try:
        with tracer.step("navigator", "classify_intent") as step:
            agent_output = run_navigator(conversation=conversation, patient_message=patient_message)
            agent_output = safety.apply_safety_validation(agent_output=agent_output, patient_message=patient_message)
            step.metadata.update(
                intent=agent_output.intent, urgency=agent_output.urgency, action=agent_output.recommended_action
            )

        with tracer.step(_component_for(agent_output), "handle_request") as step:
            route_result = _route(conversation=conversation, patient=patient, agent_output=agent_output, patient_message=patient_message)
            step.metadata.update(
                has_sources=bool(route_result.sources),
                has_pending_action=bool(route_result.pending_action),
                escalated=route_result.escalation_id is not None,
            )
        succeeded = True
        error_type = ""
    except AgentError as exc:
        agent_output = _fallback_output_for(exc, patient_message=patient_message)
        route_result = RouteResult(response_text=agent_output.response, final_agent="navigator")
        succeeded = False
        error_type = classify_exception(exc)
        logger.warning("Navigator agent failed (%s): %s", type(exc).__name__, exc)

    route_result.response_text, route_result.escalation_id, succeeded = _apply_failure_tracking(
        conversation=conversation, succeeded=succeeded, route_result=route_result
    )

    latency_seconds = time.monotonic() - started_at

    trace_status = "escalated" if route_result.escalation_id else ("completed" if succeeded else "failed")
    tracer.finish(status=trace_status, final_agent=route_result.final_agent, error_type=error_type)

    _log_turn(conversation=conversation, agent_output=agent_output, succeeded=succeeded, latency_seconds=latency_seconds)
    _maybe_update_summary(conversation=conversation, patient_message=patient_message, response_text=route_result.response_text)

    return NavigatorTurnResult(
        response_text=route_result.response_text,
        agent_output=agent_output,
        latency_seconds=latency_seconds,
        succeeded=succeeded,
        sources=route_result.sources,
        display_urgency=route_result.display_urgency,
        appointment_data=route_result.appointment_data,
        pending_action=route_result.pending_action,
        follow_up_data=route_result.follow_up_data,
        escalation_id=route_result.escalation_id,
        request_id=str(tracer.request_id),
        final_agent=route_result.final_agent,
    )


def _component_for(agent_output: AgentOutput) -> str:
    if agent_output.intent == "GENERAL_HEALTH_INFORMATION":
        return "information"
    if agent_output.intent == "SYMPTOM_CONCERN":
        return "triage"
    if agent_output.intent in ("APPOINTMENT_REQUEST", "APPOINTMENT_CHANGE"):
        return "appointment"
    if agent_output.intent == "FOLLOW_UP_REQUEST":
        return "follow_up"
    if _wants_escalation(agent_output):
        return "escalation"
    return "navigator"


def _wants_escalation(agent_output: AgentOutput) -> bool:
    """True for a *non-emergency* human hand-off — an explicit request
    for a person, or the Navigator's own recommended_action=="ESCALATE"
    for something out of scope. Emergency escalation is a completely
    separate, already-handled path (see the pre-check above and
    _emergency_output) and never reaches here."""
    if agent_output.intent == "EMERGENCY_CONCERN":
        return False
    return agent_output.intent == "HUMAN_ASSISTANCE" or agent_output.recommended_action == "ESCALATE"


def _route(*, conversation, patient, agent_output: AgentOutput, patient_message: str) -> RouteResult:
    """Resolve the final RouteResult for a non-emergency Navigator turn,
    dispatching to a specialist agent when the intent/routing calls for
    one."""
    if agent_output.intent == "GENERAL_HEALTH_INFORMATION":
        info_result = handle_information_request(conversation=conversation, question=patient_message)
        return RouteResult(response_text=info_result.response_text, sources=info_result.sources, final_agent="information")

    if agent_output.intent == "SYMPTOM_CONCERN":
        triage_result = handle_symptom_concern(conversation=conversation, patient_message=patient_message)
        display_urgency = triage_result.urgency if triage_result.urgency != "unknown" else "normal"
        return RouteResult(response_text=triage_result.response_text, display_urgency=display_urgency, final_agent="triage")

    if agent_output.intent in ("APPOINTMENT_REQUEST", "APPOINTMENT_CHANGE"):
        appointment_result = handle_appointment_request(
            conversation=conversation, patient=patient, patient_message=patient_message
        )
        return RouteResult(
            response_text=appointment_result.response_text,
            appointment_data=appointment_result.appointment_data,
            pending_action=appointment_result.pending_action,
            final_agent="appointment",
        )

    if agent_output.intent == "FOLLOW_UP_REQUEST":
        follow_up_result = handle_follow_up_request(conversation=conversation, patient=patient, patient_message=patient_message)
        return RouteResult(
            response_text=follow_up_result.response_text,
            pending_action=follow_up_result.pending_action,
            follow_up_data=follow_up_result.follow_up_data,
            final_agent="follow_up",
        )

    if _wants_escalation(agent_output):
        escalation_result = escalation_agent_service.handle_escalation_request(
            conversation=conversation, patient=patient, intent=agent_output.intent, urgency=agent_output.urgency
        )
        return RouteResult(
            response_text=escalation_result.response_text,
            escalation_id=escalation_result.escalation_id,
            final_agent="escalation",
        )

    if agent_output.recommended_action == "ROUTE_TO_AGENT" and agent_output.target_agent in AGENT_NOT_READY_RESPONSES:
        return RouteResult(response_text=AGENT_NOT_READY_RESPONSES[agent_output.target_agent], final_agent="navigator")

    return RouteResult(response_text=agent_output.response, final_agent="navigator")


def _apply_failure_tracking(*, conversation, succeeded: bool, route_result: RouteResult) -> tuple[str, int | None, bool]:
    """Update the conversation's consecutive-failure counter and
    auto-escalate once it crosses settings.MAX_AGENT_FAILURES_BEFORE_ESCALATION.

    Returns (final_response_text, escalation_id, succeeded) — succeeded
    is echoed back unchanged; an auto-escalation is reported as a
    successful turn (the *escalation* itself worked, even though the
    agent turns leading up to it did not).
    """
    if route_result.escalation_id is not None:
        # Already an explicit/out-of-scope escalation this turn — leave
        # the counter alone rather than double-counting.
        return route_result.response_text, route_result.escalation_id, succeeded

    if succeeded:
        if conversation.consecutive_agent_failures:
            conversation.consecutive_agent_failures = 0
            conversation.save(update_fields=["consecutive_agent_failures"])
        return route_result.response_text, None, succeeded

    conversation.consecutive_agent_failures += 1
    conversation.save(update_fields=["consecutive_agent_failures"])

    if conversation.consecutive_agent_failures < settings.MAX_AGENT_FAILURES_BEFORE_ESCALATION:
        return route_result.response_text, None, succeeded

    try:
        escalation = escalation_service.create_escalation(
            patient=conversation.patient,
            conversation=conversation,
            reason=Escalation.Reason.REPEATED_FAILURE,
            priority=Escalation.Priority.NORMAL,
        )
    except EscalationError as exc:
        logger.warning("Auto-escalation after repeated failures could not be created: %s", exc)
        return route_result.response_text, None, succeeded

    conversation.consecutive_agent_failures = 0
    conversation.save(update_fields=["consecutive_agent_failures"])

    response_text = build_escalation_response(Escalation.Reason.REPEATED_FAILURE)
    # The hand-off to a human succeeded even though the agent attempts
    # before it didn't — report this turn as successful.
    return response_text, escalation.id, True


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
