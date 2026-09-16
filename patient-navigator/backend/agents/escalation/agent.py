"""
Escalation Agent — deterministic by design (see prompts.py). Takes the
Navigator's already-validated intent/urgency signal and turns it into a
concrete, backend-authorized Escalation.
"""

from __future__ import annotations

from dataclasses import dataclass

from .prompts import build_escalation_response
from .schemas import derive_recommendation


@dataclass
class EscalationAgentResult:
    reason: str
    priority: str
    response: str


def run_escalation_agent(*, intent: str, urgency: str) -> EscalationAgentResult:
    recommendation = derive_recommendation(intent=intent, urgency=urgency)
    return EscalationAgentResult(
        reason=recommendation.reason,
        priority=recommendation.priority,
        response=build_escalation_response(recommendation.reason),
    )
