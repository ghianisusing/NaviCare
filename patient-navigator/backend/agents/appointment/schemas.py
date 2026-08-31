"""
Structured output contract for the Appointment Agent.

The agent's job is to decide *what* tool to call and with *what*
arguments — it never executes anything itself. `tool`/`arguments` here
are only a request; agents/appointment/service.py is responsible for
running them through tools.registry.execute_tool, which re-validates
everything against the tool's own schema regardless of what this parser
already checked.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from agents.core.exceptions import InvalidAgentOutputError

ACTIONS = {
    "SEARCH_DEPARTMENTS",
    "SEARCH_PROVIDERS",
    "FIND_AVAILABLE_SLOTS",
    "VIEW_APPOINTMENTS",
    "BOOK_APPOINTMENT",
    "CANCEL_APPOINTMENT",
    "RESCHEDULE_APPOINTMENT",
    "ASK_CLARIFYING_QUESTION",
    "RESPOND",
}

# Actions that map 1:1 onto a registered tool name (see
# tools/appointment_tools.py). ASK_CLARIFYING_QUESTION/RESPOND don't call
# a tool at all.
ACTION_TO_TOOL = {
    "SEARCH_DEPARTMENTS": "search_departments",
    "SEARCH_PROVIDERS": "search_providers",
    "FIND_AVAILABLE_SLOTS": "find_available_slots",
    "VIEW_APPOINTMENTS": "get_patient_appointments",
    "BOOK_APPOINTMENT": "book_appointment",
    "CANCEL_APPOINTMENT": "cancel_appointment",
    "RESCHEDULE_APPOINTMENT": "reschedule_appointment",
}

MUTATING_ACTIONS = {"BOOK_APPOINTMENT", "CANCEL_APPOINTMENT", "RESCHEDULE_APPOINTMENT"}

MAX_RESPONSE_CHARS = 2000


@dataclass
class AppointmentAgentOutput:
    action: str
    needs_clarification: bool
    response: str
    clarifying_question: str | None = None
    tool: str | None = None
    arguments: dict = field(default_factory=dict)


def parse_appointment_output(raw_text: str) -> AppointmentAgentOutput:
    start = raw_text.find("{")
    end = raw_text.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise InvalidAgentOutputError("No JSON object found in appointment agent output.")

    try:
        data = json.loads(raw_text[start : end + 1])
    except json.JSONDecodeError as exc:
        raise InvalidAgentOutputError("Appointment agent output was not valid JSON.") from exc

    if not isinstance(data, dict):
        raise InvalidAgentOutputError("Appointment agent output JSON was not an object.")

    action = data.get("action")
    if action not in ACTIONS:
        raise InvalidAgentOutputError(f"Unknown action: {action!r}")

    needs_clarification = data.get("needs_clarification")
    if not isinstance(needs_clarification, bool):
        raise InvalidAgentOutputError("needs_clarification must be a boolean.")

    clarifying_question = data.get("clarifying_question")
    if clarifying_question is not None:
        if not isinstance(clarifying_question, str):
            raise InvalidAgentOutputError("clarifying_question must be a string.")
        clarifying_question = clarifying_question.strip()[:500] or None

    if needs_clarification and not clarifying_question:
        raise InvalidAgentOutputError("needs_clarification=True requires a clarifying_question.")

    tool = data.get("tool")
    expected_tool = ACTION_TO_TOOL.get(action)
    if expected_tool is not None and not needs_clarification:
        if tool != expected_tool:
            raise InvalidAgentOutputError(f"action {action} must use tool {expected_tool!r}, got {tool!r}.")
    elif tool is not None and tool not in ACTION_TO_TOOL.values():
        raise InvalidAgentOutputError(f"Unknown tool: {tool!r}")

    arguments = data.get("arguments", {})
    if not isinstance(arguments, dict):
        raise InvalidAgentOutputError("arguments must be an object.")

    response = data.get("response")
    if not isinstance(response, str) or not response.strip():
        raise InvalidAgentOutputError("response must be a non-empty string.")
    response = response.strip()[:MAX_RESPONSE_CHARS]

    return AppointmentAgentOutput(
        action=action,
        needs_clarification=needs_clarification,
        response=response,
        clarifying_question=clarifying_question,
        tool=tool if not needs_clarification else None,
        arguments=arguments if not needs_clarification else {},
    )
