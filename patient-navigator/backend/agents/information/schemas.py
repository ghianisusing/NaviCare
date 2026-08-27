"""
Structured output contract for the Information Agent.

Deliberately smaller than the Navigator's schema — the Information
Agent only ever needs to say "here's a grounded answer" or "I don't
have enough information", plus the sources it actually retrieved (never
sources the LLM invents — see agents/information/agent.py, sources are
attached from the retrieval layer, not parsed out of the LLM response).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from agents.core.exceptions import InvalidAgentOutputError

MAX_RESPONSE_CHARS = 2000


@dataclass
class InformationOutput:
    response: str
    has_sufficient_information: bool
    sources: list[dict] = field(default_factory=list)


def parse_information_output(raw_text: str) -> tuple[str, bool]:
    """Parse the LLM's JSON output into (response, has_sufficient_information).

    Sources are intentionally not part of this parse — they're attached
    by the caller from the retrieval layer's actual results, never from
    the LLM, so a hallucinated citation can never reach the patient.
    """
    start = raw_text.find("{")
    end = raw_text.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise InvalidAgentOutputError("No JSON object found in information agent output.")

    try:
        data = json.loads(raw_text[start : end + 1])
    except json.JSONDecodeError as exc:
        raise InvalidAgentOutputError("Information agent output was not valid JSON.") from exc

    if not isinstance(data, dict):
        raise InvalidAgentOutputError("Information agent output JSON was not an object.")

    response = data.get("response")
    if not isinstance(response, str) or not response.strip():
        raise InvalidAgentOutputError("response must be a non-empty string.")

    has_sufficient_information = data.get("has_sufficient_information")
    if not isinstance(has_sufficient_information, bool):
        raise InvalidAgentOutputError("has_sufficient_information must be a boolean.")

    return response.strip()[:MAX_RESPONSE_CHARS], has_sufficient_information
