import json
from unittest import mock

from django.contrib.auth.models import User
from django.test import TestCase

from agents.core.exceptions import LLMResponseError, LLMUnavailableError
from agents.core.llm import LLMResult
from agents.navigator import service as navigator_service
from conversations.models import Conversation
from patients.models import Patient


def _payload(**overrides):
    defaults = dict(
        intent="GENERAL_HEALTH_INFORMATION",
        urgency="normal",
        needs_clarification=False,
        clarifying_question=None,
        recommended_action="RESPOND",
        target_agent=None,
        response="A fasting blood test checks your levels after not eating for a while.",
    )
    defaults.update(overrides)
    return json.dumps(defaults)


class FakeProvider:
    def __init__(self, text=None, raises=None):
        self._text = text
        self._raises = raises
        self.calls = 0

    def complete(self, **kwargs):
        self.calls += 1
        if self._raises:
            raise self._raises
        return LLMResult(text=self._text, raw={})


class HandlePatientMessageTests(TestCase):
    def setUp(self):
        user = User.objects.create_user(username="erin", password="S0meStrongPass!")
        self.patient = Patient.objects.create(user=user, first_name="Erin", last_name="Fox")
        self.conversation = Conversation.objects.create(patient=self.patient)

    @mock.patch("agents.navigator.agent.get_llm_provider")
    def test_happy_path_returns_agent_response(self, mock_get_provider):
        mock_get_provider.return_value = FakeProvider(text=_payload())

        result = navigator_service.handle_patient_message(
            conversation=self.conversation, patient_message="What does a fasting blood test mean?"
        )

        self.assertTrue(result.succeeded)
        self.assertIn("fasting blood test", result.response_text)
        self.assertEqual(result.agent_output.intent, "GENERAL_HEALTH_INFORMATION")

    @mock.patch("agents.navigator.agent.get_llm_provider")
    def test_emergency_intent_uses_fixed_safety_response(self, mock_get_provider):
        mock_get_provider.return_value = FakeProvider(
            text=_payload(intent="EMERGENCY_CONCERN", urgency="emergency", recommended_action="ESCALATE")
        )

        result = navigator_service.handle_patient_message(
            conversation=self.conversation, patient_message="I've been having chest pain and trouble breathing."
        )

        self.assertTrue(result.succeeded)
        self.assertEqual(result.agent_output.recommended_action, "ESCALATE")
        self.assertIn("urgent medical attention", result.response_text)

    @mock.patch("agents.navigator.agent.get_llm_provider")
    def test_deterministic_safety_overrides_bad_agent_classification(self, mock_get_provider):
        # Agent wrongly says "normal" for an emergency-sounding message —
        # the safety layer must still catch it.
        mock_get_provider.return_value = FakeProvider(text=_payload(urgency="normal", intent="UNKNOWN"))

        result = navigator_service.handle_patient_message(
            conversation=self.conversation, patient_message="I think I'm having a stroke, my face is drooping"
        )

        self.assertEqual(result.agent_output.urgency, "emergency")
        self.assertEqual(result.agent_output.recommended_action, "ESCALATE")

    @mock.patch("agents.navigator.agent.get_llm_provider")
    def test_llm_unavailable_falls_back_safely(self, mock_get_provider):
        mock_get_provider.return_value = FakeProvider(raises=LLMUnavailableError("down"))

        result = navigator_service.handle_patient_message(
            conversation=self.conversation, patient_message="I need to see a dermatologist."
        )

        self.assertFalse(result.succeeded)
        self.assertIn("temporarily unavailable", result.response_text)

    @mock.patch("agents.navigator.agent.get_llm_provider")
    def test_llm_unavailable_still_escalates_emergency(self, mock_get_provider):
        mock_get_provider.return_value = FakeProvider(raises=LLMUnavailableError("down"))

        result = navigator_service.handle_patient_message(
            conversation=self.conversation, patient_message="Severe chest pain, can't breathe"
        )

        self.assertFalse(result.succeeded)
        self.assertEqual(result.agent_output.recommended_action, "ESCALATE")
        self.assertIn("urgent medical attention", result.response_text)

    @mock.patch("agents.navigator.agent.get_llm_provider")
    def test_malformed_output_falls_back_safely(self, mock_get_provider):
        mock_get_provider.return_value = FakeProvider(text="not valid json")

        result = navigator_service.handle_patient_message(
            conversation=self.conversation, patient_message="What is a colonoscopy?"
        )

        self.assertFalse(result.succeeded)
        self.assertIn("unexpected problem", result.response_text)

    @mock.patch("agents.navigator.agent.get_llm_provider")
    def test_provider_error_falls_back_safely(self, mock_get_provider):
        mock_get_provider.return_value = FakeProvider(raises=LLMResponseError("bad request"))

        result = navigator_service.handle_patient_message(
            conversation=self.conversation, patient_message="What is a colonoscopy?"
        )

        self.assertFalse(result.succeeded)

    @mock.patch("agents.navigator.agent.get_llm_provider")
    def test_route_to_not_yet_built_agent_uses_temporary_message(self, mock_get_provider):
        mock_get_provider.return_value = FakeProvider(
            text=_payload(
                intent="APPOINTMENT_REQUEST",
                recommended_action="ROUTE_TO_AGENT",
                target_agent="appointment",
                response="Booking that now!",
            )
        )

        result = navigator_service.handle_patient_message(
            conversation=self.conversation, patient_message="I need to book an appointment."
        )

        self.assertNotIn("Booking that now", result.response_text)
        self.assertIn("being prepared", result.response_text)
