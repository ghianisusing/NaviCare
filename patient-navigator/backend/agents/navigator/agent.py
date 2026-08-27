"""
The Navigator Agent itself: turns (conversation context + new patient
message) into a validated AgentOutput.

This module only talks to the LLM through `agents.core.llm.LLMProvider`
and only returns validated data (via `schemas.parse_agent_output`) — it
never lets a malformed or partially-parsed result escape.
"""

from __future__ import annotations

from agents.core.context import ConversationContext, build_context
from agents.core.llm import LLMMessage, get_llm_provider
from agents.core.exceptions import AgentError

from .prompts import NAVIGATOR_SYSTEM_PROMPT
from .schemas import AgentOutput, parse_agent_output


def run_navigator(*, conversation, patient_message: str) -> AgentOutput:
    """Run one Navigator Agent turn.

    Raises `agents.core.exceptions.AgentError` subclasses on any failure
    (provider unavailable, bad response, invalid structured output).
    Callers (agents/navigator/service.py) are responsible for turning
    that into a safe fallback — this function never guesses a result.
    """
    context = build_context(conversation=conversation)
    provider = get_llm_provider()

    system_prompt = _compose_system_prompt(context)
    turns = context.history + [LLMMessage(role="user", content=patient_message)]

    result = provider.complete(system_prompt=system_prompt, messages=turns)
    return parse_agent_output(result.text)


def _compose_system_prompt(context: ConversationContext) -> str:
    if not context.summary:
        return NAVIGATOR_SYSTEM_PROMPT
    return (
        f"{NAVIGATOR_SYSTEM_PROMPT}\n\n"
        f"# Conversation summary so far\n\n{context.summary}\n\n"
        "Use this summary as background; the most recent messages below "
        "take precedence if anything conflicts."
    )


__all__ = ["run_navigator", "AgentOutput", "AgentError"]
