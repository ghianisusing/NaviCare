"""
Follow-Up Agent — mirrors agents/appointment/agent.py's bounded tool
loop: at most two LLM calls per patient turn, read-only tools (listing
follow-ups/reminders) execute inline and get grounded in a second call,
and any tool requiring confirmation (complete/cancel) is only ever
proposed here, never executed.
"""

from __future__ import annotations

from django.utils import timezone

from agents.core.context import build_context
from agents.core.llm import LLMMessage, get_llm_provider
from tools.exceptions import ToolError
from tools.registry import execute_tool

from .prompts import build_follow_up_system_prompt
from .schemas import (
    MUTATING_TOOLS_REQUIRING_CONFIRMATION,
    READ_ONLY_TOOLS,
    FollowUpAgentOutput,
    parse_follow_up_output,
)


class FollowUpAgentResult:
    def __init__(self, *, output: FollowUpAgentOutput, tool_result: dict | None, tool_name_executed: str | None):
        self.output = output
        self.tool_result = tool_result
        self.tool_name_executed = tool_name_executed


def run_follow_up_agent(*, conversation, patient, patient_message: str) -> FollowUpAgentResult:
    context = build_context(conversation=conversation)
    provider = get_llm_provider()
    system_prompt = build_follow_up_system_prompt(
        current_datetime_iso=timezone.now().isoformat(), patient_timezone=patient.timezone
    )

    turns = context.history + [LLMMessage(role="user", content=patient_message)]
    first_result = provider.complete(system_prompt=system_prompt, messages=turns, max_tokens=700, temperature=0.1)
    output = parse_follow_up_output(first_result.text)

    if output.needs_clarification or not output.tool:
        return FollowUpAgentResult(output=output, tool_result=None, tool_name_executed=None)

    if output.tool not in READ_ONLY_TOOLS:
        # create_follow_up/create_reminder execute immediately below (no
        # confirmation required); complete/cancel are proposals handled
        # by the service layer instead.
        if output.tool in MUTATING_TOOLS_REQUIRING_CONFIRMATION:
            return FollowUpAgentResult(output=output, tool_result=None, tool_name_executed=None)

        try:
            tool_result = execute_tool(output.tool, patient=patient, raw_arguments=output.arguments)
        except ToolError:
            return FollowUpAgentResult(output=output, tool_result=None, tool_name_executed=output.tool)
        return FollowUpAgentResult(output=output, tool_result=tool_result, tool_name_executed=output.tool)

    # Read-only tool: execute inline, then ground a second call in the
    # real result.
    try:
        tool_result = execute_tool(output.tool, patient=patient, raw_arguments=output.arguments)
    except ToolError:
        return FollowUpAgentResult(output=output, tool_result=None, tool_name_executed=output.tool)

    grounded_turns = turns + [
        LLMMessage(role="assistant", content=first_result.text),
        LLMMessage(
            role="user",
            content=(
                f"Tool result for {output.tool}: {tool_result}\n\n"
                "Using this real data, give your final answer in the same JSON format. "
                "If this data lets you identify a specific follow-up/reminder the patient "
                "wants to act on (e.g. exactly one matches what they described), you may "
                "propose that action now with concrete arguments from this data — otherwise "
                "use RESPOND or ASK_CLARIFYING_QUESTION."
            ),
        ),
    ]

    try:
        second_result = provider.complete(
            system_prompt=system_prompt, messages=grounded_turns, max_tokens=700, temperature=0.1
        )
        final_output = parse_follow_up_output(second_result.text)
    except Exception:  # noqa: BLE001 — degrade to the raw tool result rather than failing the turn
        final_output = output

    return FollowUpAgentResult(output=final_output, tool_result=tool_result, tool_name_executed=output.tool)


__all__ = ["run_follow_up_agent", "FollowUpAgentResult"]
