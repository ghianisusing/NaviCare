"""
Triage Service — the entry point `agents/navigator/service.py` calls
into when routing to the Triage Agent.

Even on total LLM failure, the deterministic safety layer still runs
against the raw patient message (via safety.service directly) so an
outage can never suppress an emergency escalation — mirrors the same
guarantee in agents/navigator/service.py.
"""

from __future__ import annotations

import logging
import time

from agents.core.exceptions import AgentError
from safety.service import evaluate as evaluate_safety

from .agent import TriageOutput, run_triage

logger = logging.getLogger("agents.triage")

FALLBACK_RESPONSE = "I'm having trouble processing that right now. Please try again shortly."


class TriageTurnResult:
    def __init__(self, *, response_text: str, urgency: str, succeeded: bool, latency_seconds: float):
        self.response_text = response_text
        self.urgency = urgency
        self.succeeded = succeeded
        self.latency_seconds = latency_seconds


def handle_symptom_concern(*, conversation, patient_message: str) -> TriageTurnResult:
    started_at = time.monotonic()

    try:
        triage_output: TriageOutput = run_triage(conversation=conversation, patient_message=patient_message)
        response_text = triage_output.response
        urgency = triage_output.urgency
        succeeded = True
    except AgentError as exc:
        logger.warning("Triage agent failed (%s): %s", type(exc).__name__, exc)
        decision = evaluate_safety(patient_message=patient_message, agent_severity="unknown")
        if decision.response:
            response_text = decision.response
            urgency = decision.severity
        else:
            response_text = FALLBACK_RESPONSE
            urgency = "unknown"
        succeeded = False

    latency_seconds = time.monotonic() - started_at

    logger.info(
        "triage_turn",
        extra={
            "conversation_id": conversation.id,
            "agent_type": "triage",
            "urgency": urgency,
            "success": succeeded,
            "latency_ms": round(latency_seconds * 1000),
        },
    )

    return TriageTurnResult(response_text=response_text, urgency=urgency, succeeded=succeeded, latency_seconds=latency_seconds)
