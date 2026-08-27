"""
Applies the central deterministic safety layer (safety/) on top of the
Triage Agent's own LLM-generated assessment.

Per Phase 3 principle #17: deterministic safety rules take precedence
over the LLM, and confidence is never shown to the patient. This module
enforces both — severity can only be escalated relative to what the
agent itself concluded, and the final response text is swapped for a
fixed, rule-provided message whenever a rule is the deciding factor.
"""

from __future__ import annotations

from safety.service import evaluate as evaluate_safety

from .schemas import TriageOutput


def apply_triage_safety(*, triage_output: TriageOutput, patient_message: str) -> TriageOutput:
    decision = evaluate_safety(patient_message=patient_message, agent_severity=triage_output.urgency)

    if not decision.is_escalation:
        return triage_output

    # A rule outranked the agent's own assessment — override severity
    # and use the rule's fixed response, never the LLM's original text.
    recommended_action = "SEEK_EMERGENCY_CARE" if decision.severity == "emergency" else "SEEK_PROMPT_MEDICAL_CARE"

    return TriageOutput(
        urgency=decision.severity,
        warning_signs=triage_output.warning_signs,
        needs_clarification=False,
        recommended_action=recommended_action,
        response=decision.response or triage_output.response,
        confidence=triage_output.confidence,
        clarifying_question=None,
    )
