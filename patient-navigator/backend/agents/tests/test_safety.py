from django.test import TestCase

from agents.navigator.safety import SAFETY_RESPONSE, apply_safety_validation, matches_emergency_pattern
from agents.navigator.schemas import AgentOutput


def _normal_output(**overrides):
    defaults = dict(
        intent="GENERAL_HEALTH_INFORMATION",
        urgency="normal",
        needs_clarification=False,
        recommended_action="RESPOND",
        response="Here's some general information.",
        clarifying_question=None,
        target_agent=None,
    )
    defaults.update(overrides)
    return AgentOutput(**defaults)


class MatchesEmergencyPatternTests(TestCase):
    def test_chest_pain_matches(self):
        self.assertTrue(matches_emergency_pattern("I've been having chest pain and trouble breathing."))

    def test_suicidal_ideation_matches(self):
        self.assertTrue(matches_emergency_pattern("I've been thinking about hurting myself."))

    def test_routine_question_does_not_match(self):
        self.assertFalse(matches_emergency_pattern("What does a fasting blood test mean?"))

    def test_appointment_request_does_not_match(self):
        self.assertFalse(matches_emergency_pattern("I need to see a dermatologist."))


class ApplySafetyValidationTests(TestCase):
    def test_normal_output_passes_through_unchanged(self):
        output = _normal_output()
        result = apply_safety_validation(agent_output=output, patient_message="What does blood pressure mean?")
        self.assertEqual(result, output)

    def test_deterministic_match_overrides_agent_even_if_agent_said_normal(self):
        # The agent misjudged urgency, but the deterministic layer catches it.
        output = _normal_output(intent="GENERAL_HEALTH_INFORMATION", urgency="normal")
        result = apply_safety_validation(
            agent_output=output, patient_message="I have severe chest pain and can't breathe."
        )
        self.assertEqual(result.urgency, "emergency")
        self.assertEqual(result.intent, "EMERGENCY_CONCERN")
        self.assertEqual(result.recommended_action, "ESCALATE")
        self.assertEqual(result.response, SAFETY_RESPONSE)
        self.assertFalse(result.needs_clarification)

    def test_agent_flagged_emergency_is_preserved_and_normalized(self):
        output = _normal_output(intent="EMERGENCY_CONCERN", urgency="emergency", recommended_action="ESCALATE")
        result = apply_safety_validation(agent_output=output, patient_message="I'm having trouble breathing")
        self.assertEqual(result.recommended_action, "ESCALATE")
        self.assertEqual(result.response, SAFETY_RESPONSE)

    def test_safety_response_never_contains_llm_free_text(self):
        # Guards against a future regression where the LLM's own wording
        # sneaks into the emergency path instead of the fixed message.
        output = _normal_output(response="Don't worry, that's probably nothing serious.")
        result = apply_safety_validation(agent_output=output, patient_message="I think I'm having a stroke")
        self.assertNotIn("probably nothing serious", result.response)
        self.assertEqual(result.response, SAFETY_RESPONSE)
