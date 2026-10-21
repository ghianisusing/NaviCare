"""
Regression tests: an unexpected (non-AgentError) exception during a
turn must still produce a safe reply and a finished trace, never a 500
with a trace stuck in RUNNING.
"""

from unittest import mock

from django.contrib.auth.models import User
from django.db import DatabaseError
from django.test import TestCase

from agents.navigator import service as navigator_service
from agents.tests.test_navigator_service import FakeProvider, _payload
from conversations.models import Conversation, Message
from observability.models import AgentTrace
from patients.models import Patient


class UnexpectedErrorTests(TestCase):
    def setUp(self):
        user = User.objects.create_user(username="oops", password="S0meStrongPass!")
        self.patient = Patient.objects.create(user=user, first_name="Oo", last_name="Ps")
        self.conversation = Conversation.objects.create(patient=self.patient)

    def _send(self):
        with self.assertLogs("agents.navigator", level="ERROR"):
            return navigator_service.handle_patient_message(
                conversation=self.conversation, patient_message="What is a flu shot?"
            )

    @mock.patch("agents.navigator.service.handle_information_request", side_effect=RuntimeError("bug"))
    @mock.patch("agents.navigator.agent.get_llm_provider")
    def test_bug_in_specialist_agent_returns_fallback_and_finishes_trace(self, mock_provider, _mock_info):
        mock_provider.return_value = FakeProvider(text=_payload(intent="GENERAL_HEALTH_INFORMATION"))

        result = self._send()

        self.assertFalse(result.succeeded)
        self.assertEqual(result.response_text, navigator_service.FALLBACK_INVALID_OUTPUT_RESPONSE)
        trace = AgentTrace.objects.get(request_id=result.request_id)
        self.assertEqual(trace.status, "failed")
        self.assertEqual(trace.error_type, "unknown_error")
        self.assertIsNotNone(trace.completed_at)
        self.conversation.refresh_from_db()
        self.assertEqual(self.conversation.consecutive_agent_failures, 1)

    @mock.patch(
        "agents.navigator.service.escalation_service.get_active_human_handoff", side_effect=DatabaseError("db down")
    )
    def test_error_outside_agent_calls_is_caught_by_safety_net(self, _mock_handoff):
        result = self._send()

        self.assertFalse(result.succeeded)
        self.assertEqual(result.response_text, navigator_service.FALLBACK_INVALID_OUTPUT_RESPONSE)
        trace = AgentTrace.objects.get(request_id=result.request_id)
        self.assertEqual(trace.status, "failed")
        self.assertEqual(trace.error_type, "database_error")
        self.assertIsNotNone(trace.completed_at)

    @mock.patch("agents.navigator.service.get_llm_provider", side_effect=RuntimeError("bug"))
    def test_summary_refresh_bug_does_not_break_the_turn(self, _mock_provider):
        for i in range(navigator_service.SUMMARY_UPDATE_INTERVAL):
            Message.objects.create(conversation=self.conversation, role="user", content=f"m{i}")

        with self.assertLogs("agents.navigator", level="WARNING"):
            navigator_service._maybe_update_summary(
                conversation=self.conversation, patient_message="m", response_text="r"
            )
