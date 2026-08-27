import json
from unittest import mock

from django.contrib.auth.models import User
from django.test import TestCase

from agents.core.exceptions import LLMUnavailableError
from agents.core.llm import LLMResult
from agents.triage import service as triage_service
from agents.triage.rules import apply_triage_safety
from agents.triage.schemas import TriageOutput
from conversations.models import Conversation
from patients.models import Patient
from safety.models import SafetyRule
from safety.rules import get_default_rules


def _output(**overrides):
    defaults = dict(
        urgency="routine",
        warning_signs=[],
        needs_clarification=False,
        recommended_action="PROVIDE_GENERAL_GUIDANCE",
        response="That sounds manageable at home for now.",
        confidence=0.6,
        clarifying_question=None,
    )
    defaults.update(overrides)
    return TriageOutput(**defaults)


class FakeProvider:
    def __init__(self, text=None, raises=None):
        self._text = text
        self._raises = raises

    def complete(self, **kwargs):
        if self._raises:
            raise self._raises
        return LLMResult(text=self._text, raw={})


class ApplyTriageSafetyTests(TestCase):
    def setUp(self):
        for rule_data in get_default_rules():
            SafetyRule.objects.create(**rule_data)

    def test_rule_escalates_llm_routine_assessment(self):
        triage_output = _output(urgency="routine")
        result = apply_triage_safety(triage_output=triage_output, patient_message="I have severe chest pain.")
        self.assertEqual(result.urgency, "emergency")
        self.assertEqual(result.recommended_action, "SEEK_EMERGENCY_CARE")
        self.assertFalse(result.needs_clarification)

    def test_no_rule_match_leaves_output_unchanged(self):
        triage_output = _output(urgency="routine")
        result = apply_triage_safety(triage_output=triage_output, patient_message="I have a mild cough.")
        self.assertEqual(result, triage_output)

    def test_confidence_never_shown_in_response_text(self):
        triage_output = _output(urgency="routine", confidence=0.42)
        result = apply_triage_safety(triage_output=triage_output, patient_message="I have severe chest pain.")
        self.assertNotIn("0.42", result.response)
        self.assertNotIn("%", result.response)


class HandleSymptomConcernTests(TestCase):
    def setUp(self):
        for rule_data in get_default_rules():
            SafetyRule.objects.create(**rule_data)
        user = User.objects.create_user(username="finn", password="S0meStrongPass!")
        self.patient = Patient.objects.create(user=user, first_name="Finn", last_name="Reyes")
        self.conversation = Conversation.objects.create(patient=self.patient)

    @mock.patch("agents.triage.agent.get_llm_provider")
    def test_happy_path_returns_triage_response(self, mock_get_provider):
        mock_get_provider.return_value = FakeProvider(
            text=json.dumps(
                {
                    "urgency": "routine",
                    "warning_signs": [],
                    "needs_clarification": True,
                    "clarifying_question": "How long have you had the cough?",
                    "recommended_action": "ASK_CLARIFYING_QUESTION",
                    "confidence": 0.5,
                    "response": "How long have you had the cough?",
                }
            )
        )

        result = triage_service.handle_symptom_concern(conversation=self.conversation, patient_message="I have a cough.")

        self.assertTrue(result.succeeded)
        self.assertEqual(result.urgency, "routine")

    @mock.patch("agents.triage.agent.get_llm_provider")
    def test_llm_failure_still_applies_deterministic_safety(self, mock_get_provider):
        mock_get_provider.return_value = FakeProvider(raises=LLMUnavailableError("down"))

        result = triage_service.handle_symptom_concern(
            conversation=self.conversation, patient_message="I have severe chest pain and can't breathe."
        )

        self.assertFalse(result.succeeded)
        self.assertEqual(result.urgency, "emergency")

    @mock.patch("agents.triage.agent.get_llm_provider")
    def test_llm_failure_without_emergency_uses_generic_fallback(self, mock_get_provider):
        mock_get_provider.return_value = FakeProvider(raises=LLMUnavailableError("down"))

        result = triage_service.handle_symptom_concern(conversation=self.conversation, patient_message="I have a mild cough.")

        self.assertFalse(result.succeeded)
        self.assertIn("trouble processing", result.response_text)
