from django.test import TestCase

from safety.models import SafetyRule
from safety.rules import get_default_rules
from safety.service import evaluate


class EvaluateTests(TestCase):
    def setUp(self):
        for rule_data in get_default_rules():
            SafetyRule.objects.create(**rule_data)

    def test_rule_escalates_over_agent_informational_assessment(self):
        decision = evaluate(patient_message="I have severe chest pain.", agent_severity="informational")
        self.assertEqual(decision.severity, "emergency")
        self.assertTrue(decision.is_escalation)
        self.assertIsNotNone(decision.response)

    def test_agent_emergency_assessment_is_not_downgraded_by_lack_of_rule_match(self):
        # No rule matches this exact phrasing, but the agent itself already
        # said "emergency" — safety must never downgrade that.
        decision = evaluate(patient_message="something ambiguous", agent_severity="emergency")
        self.assertEqual(decision.severity, "emergency")
        self.assertFalse(decision.is_escalation)

    def test_agent_and_rule_agree_is_not_flagged_as_escalation(self):
        decision = evaluate(patient_message="I have severe chest pain.", agent_severity="emergency")
        self.assertEqual(decision.severity, "emergency")
        self.assertFalse(decision.is_escalation)

    def test_no_match_and_normal_agent_assessment_stays_informational(self):
        decision = evaluate(patient_message="What is blood pressure?", agent_severity="informational")
        self.assertEqual(decision.severity, "informational")
        self.assertFalse(decision.is_escalation)
        self.assertIsNone(decision.response)

    def test_unknown_agent_severity_can_still_be_escalated(self):
        decision = evaluate(patient_message="I can't stop bleeding.", agent_severity="unknown")
        self.assertEqual(decision.severity, "emergency")
        self.assertTrue(decision.is_escalation)
