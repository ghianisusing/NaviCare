"""Exception types for the agent layer.

Kept separate from core.exceptions (which handles DRF/HTTP concerns) —
these represent failures inside the agent pipeline itself, before
anything reaches a view.
"""


class AgentError(Exception):
    """Base class for all agent-layer failures."""


class LLMUnavailableError(AgentError):
    """The LLM provider could not be reached or timed out."""


class LLMResponseError(AgentError):
    """The LLM provider returned something we can't use (bad HTTP status,
    empty completion, provider-side error payload, etc.)."""


class InvalidAgentOutputError(AgentError):
    """The LLM's output could not be parsed into the required schema, or
    failed validation once parsed (e.g. an intent value outside the
    allowed set). Callers must treat this as "no usable result" and fall
    back to a safe default — never pass the raw value through."""
