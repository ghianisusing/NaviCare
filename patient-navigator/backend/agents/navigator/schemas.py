"""
The Navigator Agent's structured output contract.

The LLM is asked to return JSON matching this shape, but the JSON is
never trusted as-is: `parse_agent_output` validates every field against
a fixed allow-list before anything downstream (safety validation, chat
service, database) is allowed to see it. Anything that doesn't validate
is rejected wholesale — see agents/navigator/service.py for the fallback
that kicks in when that happens.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from agents.core.exceptions import InvalidAgentOutputError

INTENTS = {
    "GENERAL_HEALTH_INFORMATION",
    "SYMPTOM_CONCERN",
    "APPOINTMENT_REQUEST",
    "APPOINTMENT_CHANGE",
    "LAB_RESULT_FOLLOWUP",
    "MEDICATION_INFORMATION",
    "GENERAL_NAVIGATION",
    "EMERGENCY_CONCERN",
    "HUMAN_ASSISTANCE",
    "UNKNOWN",
}

URGENCY_LEVELS = {"normal", "urgent", "emergency", "unknown"}

RECOMMENDED_ACTIONS = {"RESPOND", "ASK_CLARIFYING_QUESTION", "ROUTE_TO_AGENT", "ESCALATE"}

# `null` / None is always a valid target_agent in addition to these.
TARGET_AGENTS = {"triage", "information", "appointment", "follow_up", "escalation"}

MAX_RESPONSE_CHARS = 2000
MAX_CLARIFYING_QUESTION_CHARS = 500


@dataclass
class AgentOutput:
    intent: str
    urgency: str
    needs_clarification: bool
    recommended_action: str
    response: str
    clarifying_question: str | None = None
    target_agent: str | None = None


def parse_agent_output(raw_text: str) -> AgentOutput:
    """Parse and strictly validate the LLM's JSON output.

    Raises InvalidAgentOutputError for anything that doesn't cleanly
    match the schema — malformed JSON, missing fields, or any field
    value outside its allow-list. This function never returns a
    partially-valid result.
    """
    json_text = _extract_json_object(raw_text)

    try:
        data = json.loads(json_text)
    except (json.JSONDecodeError, TypeError) as exc:
        raise InvalidAgentOutputError("Agent output was not valid JSON.") from exc

    if not isinstance(data, dict):
        raise InvalidAgentOutputError("Agent output JSON was not an object.")

    intent = data.get("intent")
    if intent not in INTENTS:
        raise InvalidAgentOutputError(f"Unknown intent: {intent!r}")

    urgency = data.get("urgency")
    if urgency not in URGENCY_LEVELS:
        raise InvalidAgentOutputError(f"Unknown urgency: {urgency!r}")

    needs_clarification = data.get("needs_clarification")
    if not isinstance(needs_clarification, bool):
        raise InvalidAgentOutputError("needs_clarification must be a boolean.")

    recommended_action = data.get("recommended_action")
    if recommended_action not in RECOMMENDED_ACTIONS:
        raise InvalidAgentOutputError(f"Unknown recommended_action: {recommended_action!r}")

    target_agent = data.get("target_agent")
    if target_agent is not None and target_agent not in TARGET_AGENTS:
        raise InvalidAgentOutputError(f"Unknown target_agent: {target_agent!r}")

    clarifying_question = data.get("clarifying_question")
    if clarifying_question is not None:
        if not isinstance(clarifying_question, str):
            raise InvalidAgentOutputError("clarifying_question must be a string.")
        clarifying_question = clarifying_question.strip()[:MAX_CLARIFYING_QUESTION_CHARS]

    if needs_clarification and not clarifying_question:
        raise InvalidAgentOutputError("needs_clarification=True requires a clarifying_question.")

    response = data.get("response")
    if not isinstance(response, str) or not response.strip():
        raise InvalidAgentOutputError("response must be a non-empty string.")
    response = response.strip()[:MAX_RESPONSE_CHARS]

    return AgentOutput(
        intent=intent,
        urgency=urgency,
        needs_clarification=needs_clarification,
        recommended_action=recommended_action,
        response=response,
        clarifying_question=clarifying_question,
        target_agent=target_agent,
    )


def _extract_json_object(raw_text: str) -> str:
    """Best-effort extraction of a single top-level JSON object.

    Models occasionally wrap JSON in prose or code fences despite
    instructions not to — this trims to the outermost {...} so a good
    payload isn't rejected over incidental whitespace/fencing.
    """
    start = raw_text.find("{")
    end = raw_text.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise InvalidAgentOutputError("No JSON object found in agent output.")
    return raw_text[start : end + 1]
