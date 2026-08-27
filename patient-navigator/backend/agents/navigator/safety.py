"""
Safety validation layer.

Per the Phase 2 requirement, the LLM's own `urgency` classification is
never trusted on its own for emergencies. This module adds a
deterministic backstop on top of the agent's structured output:

1. A fixed keyword/pattern check runs against the patient's raw message,
   independent of anything the LLM said. As of Phase 3 this also
   consults the central, DB-backed safety rule set (see `safety/`) for
   additional coverage — but the local pattern list below remains the
   guaranteed fail-safe floor and is checked regardless of whether the
   central rule lookup succeeds.
2. If either check OR the agent's own output indicates a possible
   emergency, the result is forced to the escalation path — this is a
   one-way, monotonic override (safety can escalate a normal result but
   nothing here ever downgrades an emergency the LLM flagged).
3. The response text shown to the patient in that case is a fixed,
   pre-written safety message, never LLM-generated — that keeps the
   riskiest response in the whole system fully deterministic.
"""

from __future__ import annotations

import logging
import re

from .schemas import AgentOutput

logger = logging.getLogger("agents.navigator")

# Deliberately conservative and pattern-based rather than an ML
# classifier: false positives here just mean an extra "seek care" nudge,
# false negatives could mean a missed emergency, so this errs wide. This
# list is the guaranteed floor — it never depends on the database (see
# module docstring) — while safety.service additionally layers in the
# configurable, versioned rule set from the `safety` app.
_EMERGENCY_PATTERNS = [
    r"\bchest pain\b",
    r"\b(can'?t|cannot|difficulty|trouble)\s+breath",
    r"\bshort(ness)? of breath\b",
    r"\bsevere (bleeding|blood loss)\b",
    r"\bunconscious\b",
    r"\bnot breathing\b",
    r"\bstroke\b",
    r"\bface (is )?drooping\b",
    r"\bslurred speech\b",
    r"\b(suicid|kill myself|end my life)\w*\b",
    r"\bhurt(ing)?\s+myself\b",
    r"\boverdose\b",
    r"\bcan'?t stop bleeding\b",
    r"\bseizure\b",
    r"\banaphylax\w*\b",
    r"\ballergic reaction\b.*\b(throat|swelling|breath)\b",
]

_EMERGENCY_REGEX = re.compile("|".join(_EMERGENCY_PATTERNS), re.IGNORECASE)

SAFETY_RESPONSE = (
    "I'm concerned that what you're describing may need urgent medical "
    "attention. Please seek immediate care — contact your local "
    "emergency number or go to the nearest emergency department. If you "
    "are in immediate danger, please do not wait for a reply here."
)


def matches_emergency_pattern(patient_message: str) -> bool:
    if _EMERGENCY_REGEX.search(patient_message):
        return True

    # Additional coverage from the central, admin-configurable rule set.
    # Never let this lookup's failure suppress the baseline check above —
    # it only ever adds coverage, never replaces it.
    try:
        from safety.validator import classify_message

        return classify_message(patient_message).severity == "emergency"
    except Exception:  # noqa: BLE001
        logger.exception("Central safety rule lookup failed; baseline pattern check still applies.")
        return False


def apply_safety_validation(*, agent_output: AgentOutput, patient_message: str) -> AgentOutput:
    """Return a (possibly overridden) AgentOutput safe to show the patient."""
    deterministic_flag = matches_emergency_pattern(patient_message)
    agent_flagged_emergency = agent_output.urgency == "emergency" or agent_output.intent == "EMERGENCY_CONCERN"

    if not (deterministic_flag or agent_flagged_emergency):
        return agent_output

    return AgentOutput(
        intent="EMERGENCY_CONCERN",
        urgency="emergency",
        needs_clarification=False,
        recommended_action="ESCALATE",
        response=SAFETY_RESPONSE,
        clarifying_question=None,
        target_agent="escalation",
    )
