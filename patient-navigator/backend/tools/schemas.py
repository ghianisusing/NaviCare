"""
Shared types for the tool-calling framework.

A `ToolSpec` is the only way a tool becomes callable — see
tools/registry.py. Nothing outside this framework lets the LLM invoke
arbitrary Python; every tool call goes through `validate_arguments`
before the handler ever runs.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from typing import Any, Callable

from .exceptions import InvalidToolArgumentsError


@dataclass
class ToolField:
    name: str
    type: str  # "str" | "int" | "date" | "datetime" | "bool"
    required: bool = True
    allowed_values: tuple | None = None


@dataclass
class ToolSpec:
    name: str
    description: str
    fields: list[ToolField]
    requires_confirmation: bool
    handler: Callable[..., Any]


def validate_arguments(spec: ToolSpec, raw_arguments: dict) -> dict:
    """Validate + coerce raw (LLM- or client-supplied) arguments against
    a ToolSpec's field definitions. Raises InvalidToolArgumentsError for
    anything that doesn't match — unknown fields, missing required
    fields, wrong types, or a value outside an allow-list.

    This is the boundary that keeps LLM-generated arguments from being
    passed straight into a Django ORM call.
    """
    if not isinstance(raw_arguments, dict):
        raise InvalidToolArgumentsError("Tool arguments must be an object.")

    known_field_names = {f.name for f in spec.fields}
    unknown = set(raw_arguments.keys()) - known_field_names
    if unknown:
        raise InvalidToolArgumentsError(f"Unknown argument(s) for {spec.name}: {sorted(unknown)}")

    validated: dict = {}
    for tool_field in spec.fields:
        if tool_field.name not in raw_arguments or raw_arguments[tool_field.name] is None:
            if tool_field.required:
                raise InvalidToolArgumentsError(f"Missing required argument '{tool_field.name}' for {spec.name}.")
            continue

        value = raw_arguments[tool_field.name]
        validated[tool_field.name] = _coerce(spec.name, tool_field, value)

    return validated


def _coerce(tool_name: str, tool_field: ToolField, value: Any) -> Any:
    try:
        if tool_field.type == "str":
            if not isinstance(value, str):
                raise ValueError
            coerced = value.strip()
        elif tool_field.type == "int":
            if isinstance(value, bool) or not isinstance(value, (int, str)):
                raise ValueError
            coerced = int(value)
        elif tool_field.type == "bool":
            if not isinstance(value, bool):
                raise ValueError
            coerced = value
        elif tool_field.type == "date":
            coerced = dt.date.fromisoformat(value) if isinstance(value, str) else None
            if coerced is None:
                raise ValueError
        elif tool_field.type == "datetime":
            coerced = dt.datetime.fromisoformat(value) if isinstance(value, str) else None
            if coerced is None:
                raise ValueError
            if coerced.tzinfo is None:
                from django.utils import timezone as dj_timezone

                coerced = dj_timezone.make_aware(coerced, dj_timezone.get_default_timezone())
        else:
            raise ValueError
    except (ValueError, TypeError) as exc:
        raise InvalidToolArgumentsError(
            f"Argument '{tool_field.name}' for {tool_name} must be a valid {tool_field.type}."
        ) from exc

    if tool_field.allowed_values is not None and coerced not in tool_field.allowed_values:
        raise InvalidToolArgumentsError(
            f"Argument '{tool_field.name}' for {tool_name} must be one of {tool_field.allowed_values}."
        )

    return coerced
