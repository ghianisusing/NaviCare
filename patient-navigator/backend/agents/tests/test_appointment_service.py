import json
from datetime import timedelta
from unittest import mock

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from agents.appointment import service as appointment_agent_service
from agents.core.exceptions import LLMUnavailableError
from agents.core.llm import LLMResult
from appointments.models import AgentAction, Appointment, Availability, Department, Provider
from conversations.models import Conversation
from patients.models import Patient

import tools.appointment_tools  # noqa: F401


class SequentialFakeProvider:
    def __init__(self, texts=None, raises=None):
        self._texts = list(texts or [])
        self._raises = raises
        self.call_count = 0

    def complete(self, **kwargs):
        if self._raises:
            raise self._raises
        text = self._texts[min(self.call_count, len(self._texts) - 1)]
        self.call_count += 1
        return LLMResult(text=text, raw={})


class HandleAppointmentRequestTests(TestCase):
    def setUp(self):
        self.department = Department.objects.create(name="Orthopedics")
        self.provider = Provider.objects.create(
            department=self.department, first_name="Samuel", last_name="Okafor", title="MD", active=True
        )
        start = (timezone.now() + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)
        Availability.objects.create(provider=self.provider, start_time=start, end_time=start + timedelta(hours=1))
        self.start = start
        self.end = start + timedelta(minutes=30)

        user = User.objects.create_user(username="apptservice", password="S0meStrongPass!")
        self.patient = Patient.objects.create(user=user, first_name="Appt", last_name="Service")
        self.conversation = Conversation.objects.create(patient=self.patient)

    @mock.patch("agents.appointment.agent.get_llm_provider")
    def test_booking_request_creates_pending_action_not_a_real_appointment(self, mock_get_provider):
        payload = json.dumps(
            {
                "action": "BOOK_APPOINTMENT",
                "needs_clarification": False,
                "clarifying_question": None,
                "tool": "book_appointment",
                "arguments": {
                    "provider_id": self.provider.id,
                    "start_time": self.start.isoformat(),
                    "end_time": self.end.isoformat(),
                },
                "response": "You're about to book with Dr. Okafor.",
            }
        )
        mock_get_provider.return_value = SequentialFakeProvider([payload])

        result = appointment_agent_service.handle_appointment_request(
            conversation=self.conversation, patient=self.patient, patient_message="Book that appointment."
        )

        self.assertTrue(result.succeeded)
        self.assertIsNotNone(result.pending_action)
        self.assertEqual(Appointment.objects.count(), 0)  # not executed
        self.assertEqual(AgentAction.objects.filter(status=AgentAction.Status.VALIDATED).count(), 1)

    @mock.patch("agents.appointment.agent.get_llm_provider")
    def test_booking_request_for_unknown_provider_fails_gracefully(self, mock_get_provider):
        payload = json.dumps(
            {
                "action": "BOOK_APPOINTMENT",
                "needs_clarification": False,
                "clarifying_question": None,
                "tool": "book_appointment",
                "arguments": {
                    "provider_id": 999999,
                    "start_time": self.start.isoformat(),
                    "end_time": self.end.isoformat(),
                },
                "response": "You're about to book.",
            }
        )
        mock_get_provider.return_value = SequentialFakeProvider([payload])

        result = appointment_agent_service.handle_appointment_request(
            conversation=self.conversation, patient=self.patient, patient_message="Book that appointment."
        )

        self.assertTrue(result.succeeded)
        self.assertIsNone(result.pending_action)
        self.assertIn("couldn't find that provider", result.response_text)

    @mock.patch("agents.appointment.agent.get_llm_provider")
    def test_cancel_request_for_appointment_owned_by_another_patient_fails_gracefully(self, mock_get_provider):
        other_user = User.objects.create_user(username="otherpatient", password="S0meStrongPass!")
        other_patient = Patient.objects.create(user=other_user, first_name="Other", last_name="Patient")
        other_appointment = Appointment.objects.create(
            patient=other_patient, provider=self.provider, start_time=self.start, end_time=self.end
        )

        payload = json.dumps(
            {
                "action": "CANCEL_APPOINTMENT",
                "needs_clarification": False,
                "clarifying_question": None,
                "tool": "cancel_appointment",
                "arguments": {"appointment_id": other_appointment.id},
                "response": "Cancelling that now.",
            }
        )
        mock_get_provider.return_value = SequentialFakeProvider([payload])

        result = appointment_agent_service.handle_appointment_request(
            conversation=self.conversation, patient=self.patient, patient_message="Cancel appointment X."
        )

        self.assertIsNone(result.pending_action)
        other_appointment.refresh_from_db()
        self.assertEqual(other_appointment.status, "scheduled")  # untouched

    @mock.patch("agents.appointment.agent.get_llm_provider")
    def test_llm_failure_falls_back_safely(self, mock_get_provider):
        mock_get_provider.return_value = SequentialFakeProvider(raises=LLMUnavailableError("down"))

        result = appointment_agent_service.handle_appointment_request(
            conversation=self.conversation, patient=self.patient, patient_message="I need an appointment."
        )

        self.assertFalse(result.succeeded)
        self.assertIn("trouble processing", result.response_text)

    @mock.patch("agents.appointment.agent.get_llm_provider")
    def test_clarifying_question_produces_no_pending_action(self, mock_get_provider):
        payload = json.dumps(
            {
                "action": "ASK_CLARIFYING_QUESTION",
                "needs_clarification": True,
                "clarifying_question": "What department are you looking for?",
                "tool": None,
                "arguments": {},
                "response": "What department are you looking for?",
            }
        )
        mock_get_provider.return_value = SequentialFakeProvider([payload])

        result = appointment_agent_service.handle_appointment_request(
            conversation=self.conversation, patient=self.patient, patient_message="I need an appointment."
        )

        self.assertIsNone(result.pending_action)
        self.assertIn("department", result.response_text)
