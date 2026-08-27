"""
Combines the DB-backed SafetyRule table with a hardcoded fail-safe
baseline into a single deterministic classification.

Design intent: the database is the editable source of truth for safety
rules (an admin can add/tune rules without a deploy), but a database
outage, empty table, or query failure must never silently disable
emergency detection. `_BASELINE_EMERGENCY_PATTERN` is therefore always
checked in addition to the DB rules, not instead of them — this
function only ever adds coverage, never depends on the DB being
healthy for the emergency case.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from .models import SafetyRule
from .rules import EMERGENCY_RESPONSE

logger = logging.getLogger("safety")

SEVERITY_ORDER = {
    "informational": 0,
    "routine": 1,
    "unknown": 1,  # treated like "routine" for ordering purposes only
    "urgent": 2,
    "emergency": 3,
}

# Guaranteed to be checked regardless of database state. Deliberately a
# subset of safety/rules.py's emergency patterns — this is the fail-safe
# floor, not a replacement for the full configurable rule set.
_BASELINE_EMERGENCY_PATTERN = re.compile(
    r"\bchest pain\b|\b(can'?t|cannot|difficulty|trouble)\s+breath|\bnot breathing\b"
    r"|\bstroke\b|\bsevere (bleeding|blood loss)\b|\bunconscious\b"
    r"|\b(suicid|kill myself|end my life)\w*\b|\bhurt(ing)?\s+myself\b|\bseizure\b",
    re.IGNORECASE,
)


@dataclass
class SafetyClassification:
    severity: str  # one of SEVERITY_ORDER keys (never "unknown" as an output)
    matched_rule_names: list[str]
    response: str | None  # fixed response text if severity implies one, else None


def classify_message(patient_message: str) -> SafetyClassification:
    """Evaluate a raw patient message against all active safety rules
    plus the hardcoded baseline, returning the highest-severity match.

    Never raises for "no match found" — returns severity="informational"
    with an empty match list in that case. Database errors are caught
    and logged; the baseline check still runs regardless.
    """
    best_severity = "informational"
    best_response = None
    matched_names: list[str] = []

    try:
        for rule in SafetyRule.objects.filter(active=True):
            try:
                if re.search(rule.trigger, patient_message, re.IGNORECASE):
                    matched_names.append(rule.name)
                    if SEVERITY_ORDER[rule.severity] > SEVERITY_ORDER[best_severity]:
                        best_severity = rule.severity
                        best_response = rule.response
            except re.error:
                logger.warning("Safety rule %r has an invalid regex; skipping.", rule.name)
    except Exception:  # noqa: BLE001 — DB errors must not disable the baseline check
        logger.exception("Safety rule lookup failed; falling back to baseline pattern only.")

    if _BASELINE_EMERGENCY_PATTERN.search(patient_message):
        matched_names.append("baseline_emergency_fallback")
        if SEVERITY_ORDER["emergency"] > SEVERITY_ORDER[best_severity]:
            best_severity = "emergency"
            best_response = EMERGENCY_RESPONSE

    return SafetyClassification(severity=best_severity, matched_rule_names=matched_names, response=best_response)


def is_at_least(severity: str, floor: str) -> bool:
    """True if `severity` is >= `floor` in the safety hierarchy."""
    return SEVERITY_ORDER.get(severity, 0) >= SEVERITY_ORDER.get(floor, 0)
