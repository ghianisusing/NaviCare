import json
from datetime import timedelta
from unittest import mock

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from agents.core.exceptions import LLMUnavailableError
from agents.core.llm import LLMResult
from agents.follow_up import service as follow_up_agent_service
from agents.follow_up.agent import run_follow_up_agent
from appointments.models import AgentAction
from conversations.models import Conversation
from follow_ups.services import follow_up_service
from patients.models import Patient

import tools.follow_up_tools  # noqa: F401


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


def _get_reminders_payload():
    return json.dumps(
        {
            "action": "GET_REMINDERS",
            "needs_clarification": False,
            "clarifying_question": None,
            "tool": "get_reminders",
            "arguments": {},
            "response": "Let me check your reminders.",
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


class RunFollowUpAgentTests(TestCase):
    def setUp(self):
        user = User.objects.create_user(username="fu_agent", password="S0meStrongPass!")
        self.patient = Patient.objects.create(user=user, first_name="Fu", last_name="Agent")
        self.conversation = Conversation.objects.create(patient=self.patient)

    @mock.patch("agents.follow_up.agent.get_llm_provider")
    def test_read_only_tool_grounds_second_call(self, mock_get_provider):
        follow_up = follow_up_service.create_follow_up(patient=self.patient, title="Contact clinic")
        follow_up_service.create_reminder(
            patient=self.patient, follow_up_id=follow_up.id, scheduled_for=timezone.now() + timedelta(hours=3)
        )

        provider = SequentialFakeProvider([_get_reminders_payload(), _respond_payload("You have one reminder.")])
        mock_get_provider.return_value = provider

        result = run_follow_up_agent(
            conversation=self.conversation, patient=self.patient, patient_message="What reminders do I have?"
        )

        self.assertEqual(provider.call_count, 2)
        self.assertIsNotNone(result.tool_result)
        self.assertEqual(len(result.tool_result["reminders"]), 1)

    @mock.patch("agents.follow_up.agent.get_llm_provider")
    def test_create_follow_up_executes_immediately(self, mock_get_provider):
        payload = json.dumps(
            {
                "action": "CREATE_FOLLOW_UP",
                "needs_clarification": False,
                "clarifying_question": None,
                "tool": "create_follow_up",
                "arguments": {"title": "Contact clinic about results"},
                "response": "I've created that follow-up for you.",
            }
        )
        mock_get_provider.return_value = SequentialFakeProvider([payload])

        result = run_follow_up_agent(
            conversation=self.conversation, patient=self.patient, patient_message="Remind me to contact the clinic."
        )

        self.assertIsNotNone(result.tool_result)
        self.assertEqual(result.tool_result["follow_up"]["title"], "Contact clinic about results")

    @mock.patch("agents.follow_up.agent.get_llm_provider")
    def test_cancel_follow_up_is_proposed_not_executed(self, mock_get_provider):
        follow_up = follow_up_service.create_follow_up(patient=self.patient, title="Contact clinic")
        payload = json.dumps(
            {
                "action": "CANCEL_FOLLOW_UP",
                "needs_clarification": False,
                "clarifying_question": None,
                "tool": "cancel_follow_up",
                "arguments": {"follow_up_id": follow_up.id},
                "response": "You're about to cancel that follow-up.",
            }
        )
        mock_get_provider.return_value = SequentialFakeProvider([payload])

        result = run_follow_up_agent(
            conversation=self.conversation, patient=self.patient, patient_message="Cancel that reminder."
        )

        self.assertEqual(result.output.tool, "cancel_follow_up")
        self.assertIsNone(result.tool_result)  # never executed here
        follow_up.refresh_from_db()
        self.assertEqual(follow_up.status, "pending")


class HandleFollowUpRequestTests(TestCase):
    def setUp(self):
        user = User.objects.create_user(username="fu_service", password="S0meStrongPass!")
        self.patient = Patient.objects.create(user=user, first_name="Fu", last_name="Service")
        self.conversation = Conversation.objects.create(patient=self.patient)

    @mock.patch("agents.follow_up.agent.get_llm_provider")
    def test_complete_follow_up_creates_pending_action(self, mock_get_provider):
        follow_up = follow_up_service.create_follow_up(patient=self.patient, title="Contact clinic")
        payload = json.dumps(
            {
                "action": "COMPLETE_FOLLOW_UP",
                "needs_clarification": False,
                "clarifying_question": None,
                "tool": "complete_follow_up",
                "arguments": {"follow_up_id": follow_up.id},
                "response": "Marking that complete — confirm?",
            }
        )
        mock_get_provider.return_value = SequentialFakeProvider([payload])

        result = follow_up_agent_service.handle_follow_up_request(
            conversation=self.conversation, patient=self.patient, patient_message="I already did that."
        )

        self.assertTrue(result.succeeded)
        self.assertIsNotNone(result.pending_action)
        follow_up.refresh_from_db()
        self.assertEqual(follow_up.status, "pending")  # not executed yet
        self.assertEqual(
            AgentAction.objects.filter(status=AgentAction.Status.VALIDATED, agent="follow_up").count(), 1
        )

    @mock.patch("agents.follow_up.agent.get_llm_provider")
    def test_cancel_reminder_for_other_patient_fails_gracefully(self, mock_get_provider):
        other_user = User.objects.create_user(username="fu_other", password="S0meStrongPass!")
        other_patient = Patient.objects.create(user=other_user, first_name="Other", last_name="Patient")
        other_follow_up = follow_up_service.create_follow_up(patient=other_patient, title="Other's task")
        other_reminder = follow_up_service.create_reminder(
            patient=other_patient, follow_up_id=other_follow_up.id, scheduled_for=timezone.now() + timedelta(hours=1)
        )

        payload = json.dumps(
            {
                "action": "CANCEL_REMINDER",
                "needs_clarification": False,
                "clarifying_question": None,
                "tool": "cancel_reminder",
                "arguments": {"reminder_id": other_reminder.id},
                "response": "Cancelling that reminder.",
            }
        )
        mock_get_provider.return_value = SequentialFakeProvider([payload])

        result = follow_up_agent_service.handle_follow_up_request(
            conversation=self.conversation, patient=self.patient, patient_message="Cancel reminder X."
        )

        self.assertIsNone(result.pending_action)
        other_reminder.refresh_from_db()
        self.assertEqual(other_reminder.status, "scheduled")  # untouched

    @mock.patch("agents.follow_up.agent.get_llm_provider")
    def test_llm_failure_falls_back_safely(self, mock_get_provider):
        mock_get_provider.return_value = SequentialFakeProvider(raises=LLMUnavailableError("down"))

        result = follow_up_agent_service.handle_follow_up_request(
            conversation=self.conversation, patient=self.patient, patient_message="What reminders do I have?"
        )

        self.assertFalse(result.succeeded)
        self.assertIn("trouble processing", result.response_text)
