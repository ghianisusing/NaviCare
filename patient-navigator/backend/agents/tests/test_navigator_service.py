import json
from unittest import mock

from django.contrib.auth.models import User
from django.test import TestCase

from agents.core.exceptions import LLMResponseError, LLMUnavailableError
from agents.core.llm import LLMResult
from agents.information.service import InformationTurnResult
from agents.navigator import service as navigator_service
from agents.triage.service import TriageTurnResult
from conversations.models import Conversation
from patients.models import Patient


def _payload(**overrides):
    defaults = dict(
        intent="GENERAL_NAVIGATION",
        urgency="normal",
        needs_clarification=False,
        clarifying_question=None,
        recommended_action="RESPOND",
        target_agent=None,
        response="I can help you figure out your next steps.",
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
            conversation=self.conversation, patient_message="I don't know what department I need."
        )

        self.assertTrue(result.succeeded)
        self.assertIn("next steps", result.response_text)
        self.assertEqual(result.agent_output.intent, "GENERAL_NAVIGATION")

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

    def test_emergency_pre_check_skips_navigator_llm_entirely(self):
        # No mock provider set up at all — if the Navigator LLM were called,
        # this would raise (LLM_API_KEY unset in tests). The pre-check
        # should short-circuit before that ever happens.
        result = navigator_service.handle_patient_message(
            conversation=self.conversation, patient_message="I have severe chest pain and can't breathe."
        )
        self.assertTrue(result.succeeded)
        self.assertEqual(result.agent_output.recommended_action, "ESCALATE")
        self.assertIn("urgent medical attention", result.response_text)

    @mock.patch("agents.navigator.agent.get_llm_provider")
    def test_deterministic_safety_overrides_bad_agent_classification(self, mock_get_provider):
        # Agent wrongly says "normal" for an emergency-sounding message —
        # the pre-check should catch it before the LLM is even asked.
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

        self.assertTrue(result.succeeded)  # caught by the pre-check, never reaches the LLM
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
                intent="HUMAN_ASSISTANCE",
                recommended_action="ROUTE_TO_AGENT",
                target_agent="escalation",
                response="Connecting you now!",
            )
        )

        result = navigator_service.handle_patient_message(
            conversation=self.conversation, patient_message="Can I talk to a human?"
        )

        self.assertNotIn("Connecting you now", result.response_text)
        self.assertIn("being prepared", result.response_text)


class NavigatorRoutingTests(TestCase):
    """Phase 3: GENERAL_HEALTH_INFORMATION -> information, SYMPTOM_CONCERN -> triage."""

    def setUp(self):
        user = User.objects.create_user(username="gwen", password="S0meStrongPass!")
        self.patient = Patient.objects.create(user=user, first_name="Gwen", last_name="Cole")
        self.conversation = Conversation.objects.create(patient=self.patient)

    @mock.patch("agents.navigator.service.handle_information_request")
    @mock.patch("agents.navigator.agent.get_llm_provider")
    def test_general_health_information_routes_to_information_agent(self, mock_get_provider, mock_handle_info):
        mock_get_provider.return_value = FakeProvider(text=_payload(intent="GENERAL_HEALTH_INFORMATION"))
        mock_handle_info.return_value = InformationTurnResult(
            response_text="A blood test measures various things in your blood.",
            sources=[{"title": "Blood Tests", "source": "Test Source", "source_url": "https://example.com"}],
            succeeded=True,
            latency_seconds=0.01,
        )

        result = navigator_service.handle_patient_message(
            conversation=self.conversation, patient_message="What is a blood test?"
        )

        mock_handle_info.assert_called_once()
        self.assertIn("blood test", result.response_text)
        self.assertEqual(len(result.sources), 1)

    @mock.patch("agents.navigator.service.handle_symptom_concern")
    @mock.patch("agents.navigator.agent.get_llm_provider")
    def test_symptom_concern_routes_to_triage_agent(self, mock_get_provider, mock_handle_triage):
        mock_get_provider.return_value = FakeProvider(text=_payload(intent="SYMPTOM_CONCERN"))
        mock_handle_triage.return_value = TriageTurnResult(
            response_text="How long have you had this cough?",
            urgency="routine",
            succeeded=True,
            latency_seconds=0.01,
        )

        result = navigator_service.handle_patient_message(
            conversation=self.conversation, patient_message="I've had a cough for three days."
        )

        mock_handle_triage.assert_called_once()
        self.assertIn("cough", result.response_text)
        self.assertEqual(result.display_urgency, "routine")

    @mock.patch("agents.navigator.service.handle_appointment_request")
    @mock.patch("agents.navigator.agent.get_llm_provider")
    def test_appointment_request_routes_to_appointment_agent(self, mock_get_provider, mock_handle_appointment):
        from agents.appointment.service import AppointmentTurnResult

        mock_get_provider.return_value = FakeProvider(text=_payload(intent="APPOINTMENT_REQUEST"))
        mock_handle_appointment.return_value = AppointmentTurnResult(
            response_text="Let me find a dermatologist for you.",
            appointment_data={"type": "slot_options", "slots": []},
            pending_action=None,
            succeeded=True,
            latency_seconds=0.01,
        )

        result = navigator_service.handle_patient_message(
            conversation=self.conversation, patient_message="I need to see a dermatologist."
        )

        mock_handle_appointment.assert_called_once()
        self.assertIn("dermatologist", result.response_text)
        self.assertEqual(result.appointment_data["type"], "slot_options")

    @mock.patch("agents.navigator.service.handle_appointment_request")
    @mock.patch("agents.navigator.agent.get_llm_provider")
    def test_appointment_change_routes_to_appointment_agent(self, mock_get_provider, mock_handle_appointment):
        from agents.appointment.service import AppointmentTurnResult

        mock_get_provider.return_value = FakeProvider(text=_payload(intent="APPOINTMENT_CHANGE"))
        mock_handle_appointment.return_value = AppointmentTurnResult(
            response_text="Which appointment would you like to reschedule?",
            appointment_data=None,
            pending_action=None,
            succeeded=True,
            latency_seconds=0.01,
        )

        result = navigator_service.handle_patient_message(
            conversation=self.conversation, patient_message="I need to move my appointment."
        )

        mock_handle_appointment.assert_called_once()
        self.assertIn("reschedule", result.response_text)

    @mock.patch("agents.navigator.service.handle_follow_up_request")
    @mock.patch("agents.navigator.agent.get_llm_provider")
    def test_follow_up_request_routes_to_follow_up_agent(self, mock_get_provider, mock_handle_follow_up):
        from agents.follow_up.service import FollowUpTurnResult

        mock_get_provider.return_value = FakeProvider(text=_payload(intent="FOLLOW_UP_REQUEST"))
        mock_handle_follow_up.return_value = FollowUpTurnResult(
            response_text="You have one upcoming reminder.",
            follow_up_data={"type": "reminder_list", "reminders": []},
            pending_action=None,
            succeeded=True,
            latency_seconds=0.01,
        )

        result = navigator_service.handle_patient_message(
            conversation=self.conversation, patient_message="What reminders do I have?"
        )

        mock_handle_follow_up.assert_called_once()
        self.assertIn("reminder", result.response_text)
        self.assertEqual(result.follow_up_data["type"], "reminder_list")

    def test_emergency_pre_check_takes_precedence_over_appointment_wording(self):
        # A message that both requests an appointment AND describes an
        # emergency must never proceed with routine scheduling — safety
        # takes precedence over convenience (Phase 4 spec section 19).
        # No LLM provider mocked at all: if the appointment/navigator
        # LLM path were reached, this would raise.
        result = navigator_service.handle_patient_message(
            conversation=self.conversation,
            patient_message="I'm having severe chest pain, can you book me an appointment next month?",
        )
        self.assertTrue(result.succeeded)
        self.assertEqual(result.agent_output.recommended_action, "ESCALATE")
        self.assertIn("urgent medical attention", result.response_text)
