"""Exceptions raised by the tool-calling framework."""


class ToolError(Exception):
    """Base class for all tool-layer failures."""


class ToolNotFoundError(ToolError):
    """The requested tool name is not in the registry — the LLM
    requested something that doesn't exist and must be rejected."""


class InvalidToolArgumentsError(ToolError):
    """Tool arguments failed schema validation."""


class ToolAuthorizationError(ToolError):
    """The requesting patient is not authorized to perform this action
    (e.g. the appointment doesn't belong to them)."""
