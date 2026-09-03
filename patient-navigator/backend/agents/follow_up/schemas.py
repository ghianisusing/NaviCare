"""
Structured output contract for the Follow-Up Agent — same pattern as
agents/appointment/schemas.py: the agent only ever proposes a tool
request, never executes it. `tool`/`arguments` are validated again by
tools/registry.py before anything runs.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from agents.core.exceptions import InvalidAgentOutputError

ACTIONS = {
    "CREATE_FOLLOW_UP",
    "GET_FOLLOW_UPS",
    "COMPLETE_FOLLOW_UP",
    "CANCEL_FOLLOW_UP",
    "CREATE_REMINDER",
    "GET_REMINDERS",
    "CANCEL_REMINDER",
    "ASK_CLARIFYING_QUESTION",
    "RESPOND",
}

ACTION_TO_TOOL = {
    "CREATE_FOLLOW_UP": "create_follow_up",
    "GET_FOLLOW_UPS": "get_follow_ups",
    "COMPLETE_FOLLOW_UP": "complete_follow_up",
    "CANCEL_FOLLOW_UP": "cancel_follow_up",
    "CREATE_REMINDER": "create_reminder",
    "GET_REMINDERS": "get_reminders",
    "CANCEL_REMINDER": "cancel_reminder",
}

# Only cancel/complete require explicit confirmation before executing —
# creating a follow-up/reminder or reading data does not (Phase 5
# section 18: the patient's own request is sufficient for creation).
MUTATING_TOOLS_REQUIRING_CONFIRMATION = {"complete_follow_up", "cancel_follow_up", "cancel_reminder"}
READ_ONLY_TOOLS = {"get_follow_ups", "get_reminders"}

MAX_RESPONSE_CHARS = 2000


@dataclass
class FollowUpAgentOutput:
    action: str
    needs_clarification: bool
    response: str
    clarifying_question: str | None = None
    tool: str | None = None
    arguments: dict = field(default_factory=dict)


def parse_follow_up_output(raw_text: str) -> FollowUpAgentOutput:
    start = raw_text.find("{")
    end = raw_text.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise InvalidAgentOutputError("No JSON object found in follow-up agent output.")

    try:
        data = json.loads(raw_text[start : end + 1])
    except json.JSONDecodeError as exc:
        raise InvalidAgentOutputError("Follow-up agent output was not valid JSON.") from exc

    if not isinstance(data, dict):
        raise InvalidAgentOutputError("Follow-up agent output JSON was not an object.")

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

    return FollowUpAgentOutput(
        action=action,
        needs_clarification=needs_clarification,
        response=response,
        clarifying_question=clarifying_question,
        tool=tool if not needs_clarification else None,
        arguments=arguments if not needs_clarification else {},
    )
