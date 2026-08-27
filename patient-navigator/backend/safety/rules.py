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

from .models import SafetyRule

EMERGENCY_RESPONSE = (
    "I'm concerned that what you're describing may need urgent medical "
    "attention. Please seek immediate care — contact your local "
    "emergency number or go to the nearest emergency department. If you "
    "are in immediate danger, please do not wait for a reply here."
)

URGENT_RESPONSE = (
    "What you're describing sounds like it should be evaluated by a "
    "healthcare professional promptly — ideally today or as soon as "
    "you're able. If things get worse in the meantime, treat it as an "
    "emergency and seek immediate care."
)

DEFAULT_RULES = [
    # --- Emergency ---------------------------------------------------
    dict(
        name="Chest pain or difficulty breathing",
        category=SafetyRule.Category.CARDIAC_RESPIRATORY,
        trigger=r"\bchest pain\b|\b(can'?t|cannot|difficulty|trouble)\s+breath|\bshort(ness)? of breath\b|\bnot breathing\b",
        severity=SafetyRule.Severity.EMERGENCY,
        response=EMERGENCY_RESPONSE,
    ),
    dict(
        name="Stroke warning signs",
        category=SafetyRule.Category.NEUROLOGICAL,
        trigger=r"\bstroke\b|\bface (is )?drooping\b|\bslurred speech\b|\bsudden (weakness|numbness)\b|\bworst headache of my life\b",
        severity=SafetyRule.Severity.EMERGENCY,
        response=EMERGENCY_RESPONSE,
    ),
    dict(
        name="Severe bleeding or trauma",
        category=SafetyRule.Category.BLEEDING_TRAUMA,
        trigger=r"\bsevere (bleeding|blood loss)\b|\bcan'?t stop bleeding\b|\bunconscious\b",
        severity=SafetyRule.Severity.EMERGENCY,
        response=EMERGENCY_RESPONSE,
    ),
    dict(
        name="Suicidal ideation or self-harm",
        category=SafetyRule.Category.MENTAL_HEALTH_CRISIS,
        trigger=r"\b(suicid|kill myself|end my life)\w*\b|\bhurt(ing)?\s+myself\b|\boverdose\b",
        severity=SafetyRule.Severity.EMERGENCY,
        response=EMERGENCY_RESPONSE,
    ),
    dict(
        name="Seizure or loss of consciousness",
        category=SafetyRule.Category.NEUROLOGICAL,
        trigger=r"\bseizure\b|\bpassed out\b|\blost consciousness\b",
        severity=SafetyRule.Severity.EMERGENCY,
        response=EMERGENCY_RESPONSE,
    ),
    dict(
        name="Severe allergic reaction",
        category=SafetyRule.Category.ALLERGIC_REACTION,
        trigger=r"\banaphylax\w*\b|\ballergic reaction\b.*\b(throat|swelling|breath)\b",
        severity=SafetyRule.Severity.EMERGENCY,
        response=EMERGENCY_RESPONSE,
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
