"""
The single source of truth for NaviCare's hardcoded emergency patterns.

Everything that detects emergencies without the LLM uses this module:

- agents/navigator/safety.py: the pre-check that runs before any LLM call
- safety/validator.py: the fail-safe floor checked on top of DB rules
- safety/rules.py: the default emergency SafetyRules seeded into the DB

They used to keep their own copies, which had drifted apart (for
example "shortness of breath" and "overdose" were missing from the
validator's fail-safe floor). This list is the union of those copies, so
no path lost coverage when they were merged.

Pure Python on purpose: no Django models or DB access, so it keeps
working when the database doesn't. Edit patterns here only; the
equality tests in safety/tests/test_baseline.py check that every
consumer still derives from this module.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

EMERGENCY_RESPONSE = (
    "I'm concerned that what you're describing may need urgent medical "
    "attention. Please seek immediate care — contact your local "
    "emergency number or go to the nearest emergency department. If you "
    "are in immediate danger, please do not wait for a reply here."
)


@dataclass(frozen=True)
class EmergencyPatternGroup:
    rule_name: str  # SafetyRule.name used when seeding
    category: str  # a SafetyRule.Category value
    patterns: tuple[str, ...]

    @property
    def trigger(self) -> str:
        return "|".join(self.patterns)


EMERGENCY_PATTERN_GROUPS: tuple[EmergencyPatternGroup, ...] = (
    EmergencyPatternGroup(
        rule_name="Chest pain or difficulty breathing",
        category="cardiac_respiratory",
        patterns=(
            r"\bchest pain\b",
            r"\b(can'?t|cannot|difficulty|trouble)\s+breath",
            r"\bshort(ness)? of breath\b",
            r"\bnot breathing\b",
        ),
    ),
    EmergencyPatternGroup(
        rule_name="Stroke warning signs",
        category="neurological",
        patterns=(
            r"\bstroke\b",
            r"\bface (is )?drooping\b",
            r"\bslurred speech\b",
            r"\bsudden (weakness|numbness)\b",
            r"\bworst headache of my life\b",
        ),
    ),
    EmergencyPatternGroup(
        rule_name="Severe bleeding or trauma",
        category="bleeding_trauma",
        patterns=(
            r"\bsevere (bleeding|blood loss)\b",
            r"\bcan'?t stop bleeding\b",
            r"\bunconscious\b",
        ),
    ),
    EmergencyPatternGroup(
        rule_name="Suicidal ideation or self-harm",
        category="mental_health_crisis",
        patterns=(
            r"\b(suicid|kill myself|end my life)\w*\b",
            r"\bhurt(ing)?\s+myself\b",
            r"\boverdose\b",
        ),
    ),
    EmergencyPatternGroup(
        rule_name="Seizure or loss of consciousness",
        category="neurological",
        patterns=(
            r"\bseizure\b",
            r"\bpassed out\b",
            r"\blost consciousness\b",
        ),
    ),
    EmergencyPatternGroup(
        rule_name="Severe allergic reaction",
        category="allergic_reaction",
        patterns=(
            r"\banaphylax\w*\b",
            r"\ballergic reaction\b.*\b(throat|swelling|breath)\b",
        ),
    ),
)

EMERGENCY_PATTERNS: tuple[str, ...] = tuple(p for group in EMERGENCY_PATTERN_GROUPS for p in group.patterns)

EMERGENCY_REGEX = re.compile("|".join(EMERGENCY_PATTERNS), re.IGNORECASE)


def matches_baseline_emergency(text: str) -> bool:
    return EMERGENCY_REGEX.search(text) is not None
