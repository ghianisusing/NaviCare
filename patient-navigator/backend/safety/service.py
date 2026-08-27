"""
Safety Service — the single entry point other agents use for
deterministic safety checks (agents/navigator, agents/triage).

Wraps validator.classify_message() with the one invariant that matters
most: severity can only ever be escalated relative to what an agent
already believes, never downgraded. Callers pass in the agent's own
severity assessment (if any) and get back the final, safety-checked
severity plus the fixed response text to use when a rule is the
deciding factor.
"""

from __future__ import annotations

from dataclasses import dataclass

from .validator import SEVERITY_ORDER, classify_message


@dataclass
class SafetyDecision:
    severity: str
    is_escalation: bool  # True if this is more severe than the agent's own assessment
    response: str | None
    matched_rule_names: list[str]


def evaluate(*, patient_message: str, agent_severity: str = "informational") -> SafetyDecision:
    """Combine a deterministic rule classification with an agent's own
    severity assessment, keeping whichever is more severe.

    `agent_severity` should be one of the safety hierarchy values
    ("informational", "routine", "urgent", "emergency") or "unknown".
    """
    classification = classify_message(patient_message)

    agent_rank = SEVERITY_ORDER.get(agent_severity, 0)
    rule_rank = SEVERITY_ORDER.get(classification.severity, 0)

    if rule_rank >= agent_rank:
        final_severity = classification.severity
        is_escalation = rule_rank > agent_rank
        response = classification.response
    else:
        # The agent's own assessment was already more severe than any
        # rule matched — safety rules never downgrade it.
        final_severity = agent_severity
        is_escalation = False
        response = None

    return SafetyDecision(
        severity=final_severity,
        is_escalation=is_escalation,
        response=response,
        matched_rule_names=classification.matched_rule_names,
    )
