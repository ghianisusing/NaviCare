import json
from unittest import mock

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone
from datetime import timedelta

from agents.appointment.agent import run_appointment_agent
from agents.core.llm import LLMResult
from appointments.models import Availability, Department, Provider
from conversations.models import Conversation
from patients.models import Patient

import tools.appointment_tools  # noqa: F401 — registers tools


class SequentialFakeProvider:
    """Returns each text in `texts` in order, one per .complete() call."""

    def __init__(self, texts):
        self._texts = list(texts)
        self.call_count = 0

    def complete(self, **kwargs):
        text = self._texts[min(self.call_count, len(self._texts) - 1)]
        self.call_count += 1
        return LLMResult(text=text, raw={})


def _clarify_payload(question="What department are you looking for?"):
    return json.dumps(
        {
            "action": "ASK_CLARIFYING_QUESTION",
            "needs_clarification": True,
            "clarifying_question": question,
            "tool": None,
            "arguments": {},
            "response": question,
        }
    )


def _find_slots_payload(department="Dermatology"):
    return json.dumps(
        {
            "action": "FIND_AVAILABLE_SLOTS",
            "needs_clarification": False,
            "clarifying_question": None,
            "tool": "find_available_slots",
            "arguments": {"department_name": department},
            "response": "Let me find some appointments.",
        }
    )


def _respond_payload(text="Here's what I found."):
    return json.dumps(
        {
            "action": "RESPOND",
            "needs_clarification": False,
            "clarifying_question": None,
            "tool": None,
            "arguments": {},
            "response": text,
        }
    )


class RunAppointmentAgentTests(TestCase):
    def setUp(self):
        self.department = Department.objects.create(name="Dermatology")
        self.provider = Provider.objects.create(
            department=self.department, first_name="Alex", last_name="Rivera", title="MD", active=True
        )
        start = (timezone.now() + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)
        Availability.objects.create(provider=self.provider, start_time=start, end_time=start + timedelta(hours=1))

        user = User.objects.create_user(username="apptagent", password="S0meStrongPass!")
        self.patient = Patient.objects.create(user=user, first_name="Appt", last_name="Agent")
        self.conversation = Conversation.objects.create(patient=self.patient)

    @mock.patch("agents.appointment.agent.get_llm_provider")
    def test_clarification_stops_after_one_call(self, mock_get_provider):
        provider = SequentialFakeProvider([_clarify_payload()])
        mock_get_provider.return_value = provider

        result = run_appointment_agent(conversation=self.conversation, patient=self.patient, patient_message="I need an appointment.")

        self.assertTrue(result.output.needs_clarification)
        self.assertEqual(provider.call_count, 1)
        self.assertIsNone(result.tool_result)

    @mock.patch("agents.appointment.agent.get_llm_provider")
    def test_read_only_tool_executes_and_grounds_second_call(self, mock_get_provider):
        provider = SequentialFakeProvider([_find_slots_payload(), _respond_payload("Dr. Rivera has an opening tomorrow.")])
        mock_get_provider.return_value = provider

        result = run_appointment_agent(
            conversation=self.conversation, patient=self.patient, patient_message="I need a dermatologist."
        )

        self.assertEqual(provider.call_count, 2)
        self.assertIsNotNone(result.tool_result)
        self.assertGreater(len(result.tool_result["slots"]), 0)
        self.assertEqual(result.output.response, "Dr. Rivera has an opening tomorrow.")

    @mock.patch("agents.appointment.agent.get_llm_provider")
    def test_direct_mutating_request_is_not_executed(self, mock_get_provider):
        book_payload = json.dumps(
            {
                "action": "BOOK_APPOINTMENT",
                "needs_clarification": False,
                "clarifying_question": None,
                "tool": "book_appointment",
                "arguments": {
                    "provider_id": self.provider.id,
                    "start_time": "2026-09-03T10:00:00",
                    "end_time": "2026-09-03T10:30:00",
                },
                "response": "You're about to book that appointment.",
            }
        )
        provider = SequentialFakeProvider([book_payload])
        mock_get_provider.return_value = provider

        result = run_appointment_agent(
            conversation=self.conversation, patient=self.patient, patient_message="Book appointment 3 at 10am."
        )

        self.assertEqual(result.output.tool, "book_appointment")
        self.assertIsNone(result.tool_result)  # never executed by the agent itself
        self.assertEqual(provider.call_count, 1)

        from appointments.models import Appointment

        self.assertEqual(Appointment.objects.count(), 0)

    @mock.patch("agents.appointment.agent.get_llm_provider")
    def test_second_call_failure_degrades_gracefully(self, mock_get_provider):
        provider = SequentialFakeProvider([_find_slots_payload(), "not valid json this time"])
        mock_get_provider.return_value = provider

        result = run_appointment_agent(
            conversation=self.conversation, patient=self.patient, patient_message="I need a dermatologist."
        )

        # Falls back to the first call's output rather than raising.
        self.assertEqual(result.output.action, "FIND_AVAILABLE_SLOTS")
        self.assertIsNotNone(result.tool_result)
