"""
Tool Registry — the LLM can only ever invoke a tool that is registered
here. There is no code path from agent output to a Python function call
that doesn't go through `get_tool` + `validate_arguments` first.
"""

from __future__ import annotations

from .exceptions import ToolNotFoundError
from .schemas import ToolSpec, validate_arguments

_REGISTRY: dict[str, ToolSpec] = {}


def register_tool(spec: ToolSpec) -> None:
    _REGISTRY[spec.name] = spec


def get_tool(name: str) -> ToolSpec:
    try:
        return _REGISTRY[name]
    except KeyError as exc:
        raise ToolNotFoundError(f"Unknown tool: {name!r}") from exc


def list_tools() -> list[ToolSpec]:
    return list(_REGISTRY.values())


def describe_tools_for_prompt() -> str:
    """Render the registered tools as plain text for the LLM's system
    prompt — this is the *only* list of tools the model is ever shown,
    so it can't request something that isn't real."""
    lines = []
    for spec in _REGISTRY.values():
        field_descriptions = ", ".join(
            f"{f.name} ({f.type}{'' if f.required else ', optional'})" for f in spec.fields
        )
        confirmation_note = " — mutates data, requires patient confirmation" if spec.requires_confirmation else ""
        lines.append(f"- {spec.name}({field_descriptions}): {spec.description}{confirmation_note}")
    return "\n".join(lines)


def validate_and_prepare(tool_name: str, raw_arguments: dict) -> tuple[ToolSpec, dict]:
    """Look up a tool and validate its arguments in one step — the
    standard entry point for callers that are about to execute a tool."""
    spec = get_tool(tool_name)
    validated_arguments = validate_arguments(spec, raw_arguments)
    return spec, validated_arguments


def execute_tool(tool_name: str, *, patient, raw_arguments: dict) -> dict:
    """Validate arguments and run the tool's handler in one step.

    Raises ToolNotFoundError / InvalidToolArgumentsError from validation,
    or whatever the handler itself raises (typically ToolError /
    ToolAuthorizationError) — callers (agents/appointment/service.py)
    are responsible for turning those into a patient-safe response.
    """
    spec, validated_arguments = validate_and_prepare(tool_name, raw_arguments)
    return spec.handler(patient, **validated_arguments)
