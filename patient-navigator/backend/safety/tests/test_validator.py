from django.test import TestCase

from safety.models import SafetyRule
from safety.rules import get_default_rules
from safety.validator import classify_message, is_at_least


class ClassifyMessageTests(TestCase):
    def setUp(self):
        for rule_data in get_default_rules():
            SafetyRule.objects.create(**rule_data)

    def test_emergency_message_classified_as_emergency(self):
        result = classify_message("I have severe chest pain and can't breathe.")
        self.assertEqual(result.severity, "emergency")
        self.assertTrue(result.matched_rule_names)
        self.assertIsNotNone(result.response)

    def test_urgent_message_classified_as_urgent(self):
        result = classify_message("My symptoms have been getting worse over the past two days.")
        self.assertEqual(result.severity, "urgent")

    def test_routine_message_classified_as_informational(self):
        result = classify_message("What is a fasting blood test?")
        self.assertEqual(result.severity, "informational")
        self.assertEqual(result.matched_rule_names, [])
        self.assertIsNone(result.response)

    def test_inactive_rule_does_not_match(self):
        SafetyRule.objects.filter(name="Persistent high fever").update(active=False)
        result = classify_message("I have had a fever for 5 days now.")
        # Should not match on the (now inactive) fever rule specifically.
        self.assertNotIn("Persistent high fever", result.matched_rule_names)

    def test_baseline_fallback_still_matches_even_if_db_empty(self):
        SafetyRule.objects.all().delete()
        result = classify_message("I think I'm having a stroke, my face is drooping.")
        self.assertEqual(result.severity, "emergency")
        self.assertIn("baseline_emergency_fallback", result.matched_rule_names)

    def test_highest_severity_wins_when_multiple_rules_match(self):
        # Message matches both an urgent (worsening) and emergency (chest pain) rule.
        result = classify_message("My chest pain has been getting worse and I can't breathe.")
        self.assertEqual(result.severity, "emergency")


class IsAtLeastTests(TestCase):
    def test_emergency_is_at_least_urgent(self):
        self.assertTrue(is_at_least("emergency", "urgent"))

    def test_routine_is_not_at_least_urgent(self):
        self.assertFalse(is_at_least("routine", "urgent"))

    def test_equal_severity_is_at_least(self):
        self.assertTrue(is_at_least("urgent", "urgent"))
