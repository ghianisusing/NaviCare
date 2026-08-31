"""
Appointment Agent — decides what appointment action (if any) a patient's
message calls for, executing at most one read-only "lookup" tool inline
before producing its final answer.

This is a deliberately *bounded* tool loop, not an open-ended agentic
one: at most two LLM calls per patient turn.

    call 1 -> decide an action
                 |
                 +-- no tool / needs clarification -> done
                 |
                 +-- read-only tool (search/find/view) -> execute it,
                 |   then call 2 with the real result attached so the
                 |   model can phrase an accurate answer, or propose a
                 |   grounded mutating action (e.g. it now knows which
                 |   appointment matches "tomorrow")
                 |
                 +-- mutating tool requested directly (e.g. the patient
                     referenced a concrete id shown earlier in the UI)
                     -> treated as a proposal, not executed here

Nothing in this module executes a *mutating* tool — see
agents/appointment/service.py, which is the only place a mutating tool
request becomes a pending AgentAction, and tools/registry.py +
appointments/services/appointment_service.py, which are the only places
one is ever actually executed.
"""

from __future__ import annotations

from agents.core.context import build_context
from agents.core.llm import LLMMessage, get_llm_provider
from tools.exceptions import ToolError
from tools.registry import execute_tool

from .prompts import build_appointment_system_prompt
from .schemas import AppointmentAgentOutput, parse_appointment_output

READ_ONLY_TOOLS = {"search_departments", "search_providers", "find_available_slots", "get_patient_appointments"}
MUTATING_TOOLS = {"book_appointment", "cancel_appointment", "reschedule_appointment"}


class AppointmentAgentResult:
    def __init__(self, *, output: AppointmentAgentOutput, tool_result: dict | None, tool_name_executed: str | None):
        self.output = output
        self.tool_result = tool_result
        self.tool_name_executed = tool_name_executed


def run_appointment_agent(*, conversation, patient, patient_message: str) -> AppointmentAgentResult:
    """Run one Appointment Agent turn. May execute a read-only tool
    inline; never executes a mutating one.

    Raises `agents.core.exceptions.AgentError` subclasses if the first
    LLM call fails or returns unusable output. A second-call failure
    (during the read-only tool grounding step) degrades gracefully to
    the first call's output plus the raw tool result, rather than
    raising — see the fallback in the try/except below.
    """
    context = build_context(conversation=conversation)
    provider = get_llm_provider()
    system_prompt = build_appointment_system_prompt()

    turns = context.history + [LLMMessage(role="user", content=patient_message)]
    first_result = provider.complete(system_prompt=system_prompt, messages=turns, max_tokens=700, temperature=0.1)
    output = parse_appointment_output(first_result.text)

    if output.needs_clarification or not output.tool:
        return AppointmentAgentResult(output=output, tool_result=None, tool_name_executed=None)

    if output.tool in MUTATING_TOOLS:
        # Proposal only — never executed from here.
        return AppointmentAgentResult(output=output, tool_result=None, tool_name_executed=None)

    # Read-only tool: execute inline, then ground a second call in the
    # real result so the model isn't describing data it never saw.
    try:
        tool_result = execute_tool(output.tool, patient=patient, raw_arguments=output.arguments)
    except ToolError:
        # Surface as "no result" rather than raising — the caller falls
        # back to a deterministic summary of an empty result.
        return AppointmentAgentResult(output=output, tool_result=None, tool_name_executed=output.tool)

    grounded_turns = turns + [
        LLMMessage(role="assistant", content=first_result.text),
        LLMMessage(
            role="user",
            content=(
                f"Tool result for {output.tool}: {tool_result}\n\n"
                "Using this real data, give your final answer in the same JSON format. "
                "If this data lets you identify a specific appointment action the patient "
                "wants (e.g. exactly one appointment matches what they described), you may "
                "propose that mutating action now with concrete arguments from this data — "
                "otherwise use RESPOND or ASK_CLARIFYING_QUESTION."
            ),
        ),
    ]

    try:
        second_result = provider.complete(
            system_prompt=system_prompt, messages=grounded_turns, max_tokens=700, temperature=0.1
        )
        final_output = parse_appointment_output(second_result.text)
    except Exception:  # noqa: BLE001 — degrade to the raw tool result rather than failing the turn
        final_output = output

    return AppointmentAgentResult(output=final_output, tool_result=tool_result, tool_name_executed=output.tool)


__all__ = ["run_appointment_agent", "AppointmentAgentResult", "READ_ONLY_TOOLS", "MUTATING_TOOLS"]
