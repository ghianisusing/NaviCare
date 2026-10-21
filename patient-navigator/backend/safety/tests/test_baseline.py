"""
Equality tests: every hardcoded emergency check derives from
safety/baseline.py, so the copies can't drift apart again.
"""

from django.test import TestCase

from agents.navigator import safety as navigator_safety
from safety import baseline, rules, validator
from safety.models import SafetyRule


class SingleSourceOfTruthTests(TestCase):
    def test_navigator_pre_check_uses_baseline_patterns(self):
        self.assertEqual(navigator_safety._EMERGENCY_REGEX.pattern, baseline.EMERGENCY_REGEX.pattern)
        self.assertEqual(navigator_safety.SAFETY_RESPONSE, baseline.EMERGENCY_RESPONSE)

    def test_validator_floor_uses_baseline_patterns(self):
        self.assertEqual(validator._BASELINE_EMERGENCY_PATTERN.pattern, baseline.EMERGENCY_REGEX.pattern)

    def test_seeded_emergency_rules_match_baseline_exactly(self):
        seeded = {
            r["name"]: r["trigger"]
            for r in rules.get_default_rules()
            if r["severity"] == SafetyRule.Severity.EMERGENCY
        }
        expected = {g.rule_name: g.trigger for g in baseline.EMERGENCY_PATTERN_GROUPS}
        self.assertEqual(seeded, expected)

    def test_all_emergency_responses_are_identical(self):
        responses = {r["response"] for r in rules.get_default_rules() if r["severity"] == SafetyRule.Severity.EMERGENCY}
        self.assertEqual(responses, {baseline.EMERGENCY_RESPONSE})

    def test_baseline_categories_are_valid(self):
        for group in baseline.EMERGENCY_PATTERN_GROUPS:
            self.assertIn(group.category, SafetyRule.Category.values, group.rule_name)


class ConsistentDetectionTests(TestCase):
    """Phrases the old copies disagreed on. With no DB rules loaded, both
    DB-independent paths must flag every one of them."""

    PREVIOUSLY_INCONSISTENT = [
        "I have shortness of breath",  # missing from the validator floor
        "I think I took an overdose",  # missing from the validator floor
        "my face is drooping",  # missing from the validator floor
        "I can't stop bleeding",  # missing from the validator floor
        "signs of anaphylaxis",  # missing from the validator floor
        "I passed out an hour ago",  # only in the seeded DB rules
        "worst headache of my life",  # only in the seeded DB rules
        "sudden numbness in my arm",  # only in the seeded DB rules
    ]

    def test_navigator_pre_check_flags_every_baseline_phrase_without_db_rules(self):
        self.assertFalse(SafetyRule.objects.exists())
        for phrase in self.PREVIOUSLY_INCONSISTENT:
            with self.subTest(phrase=phrase):
                self.assertTrue(navigator_safety.matches_emergency_pattern(phrase))

    def test_validator_flags_every_baseline_phrase_without_db_rules(self):
        for phrase in self.PREVIOUSLY_INCONSISTENT:
            with self.subTest(phrase=phrase):
                self.assertEqual(validator.classify_message(phrase).severity, "emergency")
