"""
Context management — decides what conversation history actually gets
sent to the LLM on each turn, so callers never have to think about
context-window growth themselves.

Strategy for Phase 2 (deliberately simple; revisit if/when summarization
quality needs tuning in a later phase):

    conversation.summary (if any)
        +
    the last MAX_CONTEXT_MESSAGES messages
        +
    the current patient message

Older messages beyond the window are represented only through the
summary, not sent verbatim.
"""

from __future__ import annotations

from dataclasses import dataclass

from .llm import LLMMessage

MAX_CONTEXT_MESSAGES = 20


@dataclass
class ConversationContext:
    summary: str
    history: list[LLMMessage]


def build_context(*, conversation, max_messages: int = MAX_CONTEXT_MESSAGES) -> ConversationContext:
    """Build the bounded context for a conversation.

    `conversation` is a `conversations.models.Conversation` instance.
    Only `user` and `assistant` roles are forwarded to the LLM; any
    `system` rows (reserved for future internal annotations) are
    excluded from the turn history.
    """
    recent_messages = list(
        conversation.messages.filter(role__in=["user", "assistant"]).order_by("-created_at")[:max_messages]
    )
    recent_messages.reverse()

    history = [LLMMessage(role=m.role, content=m.content) for m in recent_messages]

    return ConversationContext(summary=conversation.summary or "", history=history)
