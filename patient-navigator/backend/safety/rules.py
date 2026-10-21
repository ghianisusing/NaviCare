"""
Default safety rule definitions, seeded into the database by
`manage.py seed_safety_rules`.

Kept as plain Python data (rather than a migration data-load) so the
canonical rule set is easy to review/diff in code review, while the
actual runtime source of truth is still the database — an admin can
add, edit, or deactivate rules without a deploy once seeded.

These are intentionally high-level, conservative warning-sign patterns,
not an exhaustive medical triage system — see the Phase 3 scope notes.
"""

from .baseline import EMERGENCY_PATTERN_GROUPS, EMERGENCY_RESPONSE
from .models import SafetyRule

URGENT_RESPONSE = (
    "What you're describing sounds like it should be evaluated by a "
    "healthcare professional promptly — ideally today or as soon as "
    "you're able. If things get worse in the meantime, treat it as an "
    "emergency and seek immediate care."
)

DEFAULT_RULES = [
    # --- Emergency ---------------------------------------------------
    # Generated from safety/baseline.py so the seeded DB rules can't drift
    # from the hardcoded fail-safe patterns.
    *(
        dict(
            name=group.rule_name,
            category=group.category,
            trigger=group.trigger,
            severity=SafetyRule.Severity.EMERGENCY,
            response=EMERGENCY_RESPONSE,
        )
        for group in EMERGENCY_PATTERN_GROUPS
    ),
    # --- Urgent --------------------------------------------------------
    dict(
        name="Persistent high fever",
        category=SafetyRule.Category.GENERAL,
        trigger=r"\bfever\b.*\b(day|days|week|weeks)\b|\bhigh fever\b|\b(103|104|105)\s*(degrees|f|°f)\b",
        severity=SafetyRule.Severity.URGENT,
        response=URGENT_RESPONSE,
    ),
    dict(
        name="Worsening symptoms",
        category=SafetyRule.Category.GENERAL,
        trigger=r"\b(getting|gotten) worse\b|\bworsening\b|\bnot improving\b",
        severity=SafetyRule.Severity.URGENT,
        response=URGENT_RESPONSE,
    ),
    dict(
        name="Severe or persistent pain",
        category=SafetyRule.Category.GENERAL,
        trigger=r"\bsevere pain\b|\bunbearable pain\b|\bworst pain\b",
        severity=SafetyRule.Severity.URGENT,
        response=URGENT_RESPONSE,
    ),
]


def get_default_rules() -> list[dict]:
    """Returns the canonical default rule set (plain dicts, unsaved)."""
    return list(DEFAULT_RULES)
