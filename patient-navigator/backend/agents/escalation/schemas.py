"""
Structured output for escalation recommendations.

This is deliberately not a full LLM structured-output roundtrip like
the other agents — the Navigator already decides *that* something
should escalate (via its existing `recommended_action=="ESCALATE"` /
`intent=="HUMAN_ASSISTANCE"` values, unchanged since Phase 2/3). This
module's job is narrower: take that signal and deterministically map it
to a validated `Escalation.Reason`, since — per Phase 6 point 6 — the
LLM can *recommend* escalation but the backend decides the actual
reason/priority recorded, rather than trusting free-form LLM text.
"""

from __future__ import annotations

from dataclasses import dataclass

from escalations.models import Escalation


@dataclass
class EscalationRecommendation:
    reason: str
    priority: str


def derive_recommendation(*, intent: str, urgency: str) -> EscalationRecommendation:
    """Map a Navigator AgentOutput's (already-validated) intent/urgency
    onto a controlled Escalation reason/priority. Never accepts a raw
    string from the LLM directly as the reason."""
    if intent == "HUMAN_ASSISTANCE":
        reason = Escalation.Reason.PATIENT_REQUEST
    elif urgency == "urgent":
        reason = Escalation.Reason.SAFETY_REVIEW
    else:
        reason = Escalation.Reason.OUT_OF_SCOPE

    priority = Escalation.Priority.HIGH if urgency in ("urgent",) else Escalation.Priority.NORMAL
    return EscalationRecommendation(reason=reason, priority=priority)
