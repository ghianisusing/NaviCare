"""
Triage Agent — assesses urgency from a patient's described symptoms,
using conversation context, then hands the result through the
deterministic safety layer before anything is returned.
"""

from __future__ import annotations

from agents.core.context import build_context
from agents.core.llm import LLMMessage, get_llm_provider

from .prompts import TRIAGE_SYSTEM_PROMPT
from .rules import apply_triage_safety
from .schemas import TriageOutput, parse_triage_output


def run_triage(*, conversation, patient_message: str) -> TriageOutput:
    """Run one Triage Agent turn, safety-checked before returning.

    Raises `agents.core.exceptions.AgentError` subclasses if the LLM
    call fails or returns unusable output — callers (agents/triage/service.py)
    are responsible for the safe fallback in that case.
    """
    context = build_context(conversation=conversation)
    provider = get_llm_provider()

    system_prompt = _compose_system_prompt(context.summary)
    turns = context.history + [LLMMessage(role="user", content=patient_message)]

    result = provider.complete(system_prompt=system_prompt, messages=turns, max_tokens=500, temperature=0.1)
    triage_output = parse_triage_output(result.text)

    return apply_triage_safety(triage_output=triage_output, patient_message=patient_message)


def _compose_system_prompt(summary: str) -> str:
    if not summary:
        return TRIAGE_SYSTEM_PROMPT
    return (
        f"{TRIAGE_SYSTEM_PROMPT}\n\n# Conversation summary so far\n\n{summary}\n\n"
        "Use this summary as background; the most recent messages take precedence."
    )


__all__ = ["run_triage", "TriageOutput"]
