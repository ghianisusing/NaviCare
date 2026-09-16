"""
Escalation Service (agent layer) — the entry point
`agents/navigator/service.py` calls into when the Navigator decides a
conversation should go to a human (intent HUMAN_ASSISTANCE, or
recommended_action ESCALATE for a non-emergency reason).
"""

from __future__ import annotations

import logging
import time

from escalations.services import escalation_service
from escalations.services.exceptions import EscalationError

from .agent import run_escalation_agent

logger = logging.getLogger("agents.escalation")


class EscalationTurnResult:
    def __init__(self, *, response_text: str, escalation_id: int | None, succeeded: bool, latency_seconds: float):
        self.response_text = response_text
        self.escalation_id = escalation_id
        self.succeeded = succeeded
        self.latency_seconds = latency_seconds


def handle_escalation_request(*, conversation, patient, intent: str, urgency: str, reason: str | None = None) -> EscalationTurnResult:
    started_at = time.monotonic()

    agent_result = run_escalation_agent(intent=intent, urgency=urgency)
    final_reason = reason or agent_result.reason

    try:
        escalation = escalation_service.create_escalation(
            patient=patient, conversation=conversation, reason=final_reason, priority=agent_result.priority
        )
        succeeded = True
        response_text = agent_result.response
        escalation_id = escalation.id
    except EscalationError as exc:
        logger.warning("Escalation creation failed (%s): %s", type(exc).__name__, exc)
        succeeded = False
        response_text = (
            "I wasn't able to connect you with our care support team just now. "
            "Please try again shortly."
        )
        escalation_id = None

    latency_seconds = time.monotonic() - started_at

    logger.info(
        "escalation_turn",
        extra={
            "conversation_id": conversation.id,
            "agent_type": "escalation",
            "reason": final_reason,
            "success": succeeded,
            "latency_ms": round(latency_seconds * 1000),
        },
    )

    return EscalationTurnResult(
        response_text=response_text, escalation_id=escalation_id, succeeded=succeeded, latency_seconds=latency_seconds
    )
