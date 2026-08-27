"""
Structured output contract for the Triage Agent.

`confidence` is explicitly an internal signal only — see
agents/triage/service.py and the frontend, neither of which ever
surfaces it to the patient. Per the Phase 3 spec, an LLM confidence
score must never be presented as a medical probability.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from agents.core.exceptions import InvalidAgentOutputError

URGENCY_LEVELS = {"routine", "urgent", "emergency", "unknown"}

RECOMMENDED_ACTIONS = {
    "SEEK_EMERGENCY_CARE",
    "SEEK_PROMPT_MEDICAL_CARE",
    "ROUTINE_FOLLOWUP",
    "ASK_CLARIFYING_QUESTION",
    "PROVIDE_GENERAL_GUIDANCE",
}

MAX_RESPONSE_CHARS = 2000
MAX_WARNING_SIGNS = 10


@dataclass
class TriageOutput:
    urgency: str
    warning_signs: list[str]
    needs_clarification: bool
    recommended_action: str
    response: str
    confidence: float
    clarifying_question: str | None = field(default=None)


def parse_triage_output(raw_text: str) -> TriageOutput:
    """Parse and strictly validate the LLM's JSON triage assessment."""
    start = raw_text.find("{")
    end = raw_text.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise InvalidAgentOutputError("No JSON object found in triage agent output.")

    try:
        data = json.loads(raw_text[start : end + 1])
    except json.JSONDecodeError as exc:
        raise InvalidAgentOutputError("Triage agent output was not valid JSON.") from exc

    if not isinstance(data, dict):
        raise InvalidAgentOutputError("Triage agent output JSON was not an object.")

    urgency = data.get("urgency")
    if urgency not in URGENCY_LEVELS:
        raise InvalidAgentOutputError(f"Unknown urgency: {urgency!r}")

    warning_signs = data.get("warning_signs")
    if not isinstance(warning_signs, list) or not all(isinstance(w, str) for w in warning_signs):
        raise InvalidAgentOutputError("warning_signs must be a list of strings.")
    warning_signs = [w.strip() for w in warning_signs if w.strip()][:MAX_WARNING_SIGNS]

    needs_clarification = data.get("needs_clarification")
    if not isinstance(needs_clarification, bool):
        raise InvalidAgentOutputError("needs_clarification must be a boolean.")

    recommended_action = data.get("recommended_action")
    if recommended_action not in RECOMMENDED_ACTIONS:
        raise InvalidAgentOutputError(f"Unknown recommended_action: {recommended_action!r}")

    clarifying_question = data.get("clarifying_question")
    if clarifying_question is not None:
        if not isinstance(clarifying_question, str):
            raise InvalidAgentOutputError("clarifying_question must be a string.")
        clarifying_question = clarifying_question.strip()[:500] or None

    if needs_clarification and not clarifying_question:
        raise InvalidAgentOutputError("needs_clarification=True requires a clarifying_question.")

    response = data.get("response")
    if not isinstance(response, str) or not response.strip():
        raise InvalidAgentOutputError("response must be a non-empty string.")
    response = response.strip()[:MAX_RESPONSE_CHARS]

    confidence = data.get("confidence")
    if not isinstance(confidence, (int, float)) or not (0.0 <= float(confidence) <= 1.0):
        raise InvalidAgentOutputError("confidence must be a number between 0 and 1.")

    return TriageOutput(
        urgency=urgency,
        warning_signs=warning_signs,
        needs_clarification=needs_clarification,
        recommended_action=recommended_action,
        response=response,
        confidence=float(confidence),
        clarifying_question=clarifying_question,
    )
