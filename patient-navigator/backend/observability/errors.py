"""
Maps exceptions raised anywhere in the agent layer to one of a
controlled set of error categories, so failures can be monitored by
type (see observability/models.py:AgentTrace.ErrorType and the
agent-metrics endpoint) instead of an unbounded set of free-text error
strings.
"""

from __future__ import annotations

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import DatabaseError

from .models import AgentTrace

ErrorType = AgentTrace.ErrorType


def classify_exception(exc: Exception) -> str:
    # Import locally to avoid every caller needing these agent-layer
    # modules as a hard dependency just to classify an error.
    from agents.core.exceptions import (
        InvalidAgentOutputError,
        LLMResponseError,
        LLMUnavailableError,
    )
    from tools.exceptions import InvalidToolArgumentsError, ToolAuthorizationError, ToolError, ToolNotFoundError

    if isinstance(exc, LLMUnavailableError):
        return ErrorType.TIMEOUT
    if isinstance(exc, LLMResponseError):
        return ErrorType.LLM_ERROR
    if isinstance(exc, InvalidAgentOutputError):
        return ErrorType.VALIDATION_ERROR
    if isinstance(exc, ToolAuthorizationError):
        return ErrorType.AUTHORIZATION_ERROR
    if isinstance(exc, (ToolNotFoundError, InvalidToolArgumentsError)):
        return ErrorType.VALIDATION_ERROR
    if isinstance(exc, ToolError):
        return ErrorType.TOOL_ERROR
    if isinstance(exc, (DatabaseError,)):
        return ErrorType.DATABASE_ERROR
    if isinstance(exc, DjangoValidationError):
        return ErrorType.VALIDATION_ERROR
    if isinstance(exc, PermissionError):
        return ErrorType.AUTHORIZATION_ERROR
    if isinstance(exc, TimeoutError):
        return ErrorType.TIMEOUT
    return ErrorType.UNKNOWN_ERROR
