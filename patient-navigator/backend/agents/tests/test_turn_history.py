"""
Regression tests: each agent must send the patient's current message to
the LLM exactly once.

The chat service saves the patient's message before calling the agents,
and each agent appends `patient_message` to the history itself. Before
the fix, `build_context` also returned that saved row, so the LLM saw
the message twice.
"""

from unittest import mock

from django.contrib.auth.models import User
from django.test import TestCase

from agents.appointment.agent import run_appointment_agent
from agents.core.exceptions import AgentError, LLMUnavailableError
from agents.follow_up.agent import run_follow_up_agent
from agents.navigator.agent import run_navigator
from agents.triage.agent import run_triage
from conversations.models import Conversation, Message
from patients.models import Patient


class RecordingProvider:
    """Records the turn list of the first call, then fails so the test
    doesn't depend on any agent's output schema."""

    def __init__(self):
        self.turns = None

    def complete(self, *, messages, **kwargs):
        self.turns = [(m.role, m.content) for m in messages]
        raise LLMUnavailableError("recorded")


EXPECTED_TURNS = [
    ("user", "My earlier question"),
    ("assistant", "My earlier answer"),
    ("user", "My new question"),
]


class AgentTurnHistoryTests(TestCase):
    def setUp(self):
        user = User.objects.create_user(username="turns", password="S0meStrongPass!")
        self.patient = Patient.objects.create(user=user, first_name="Tam", last_name="Ng")
        self.conversation = Conversation.objects.create(patient=self.patient)
        Message.objects.create(conversation=self.conversation, role="user", content="My earlier question")
        Message.objects.create(conversation=self.conversation, role="assistant", content="My earlier answer")
        # Saved by chat_service.send_message before any agent runs.
        Message.objects.create(conversation=self.conversation, role="user", content="My new question")

    def _turns_sent_by(self, module_path, run):
        provider = RecordingProvider()
        with mock.patch(f"{module_path}.get_llm_provider", return_value=provider):
            with self.assertRaises(AgentError):
                run()
        return provider.turns

    def test_navigator_sends_patient_message_once(self):
        turns = self._turns_sent_by(
            "agents.navigator.agent",
            lambda: run_navigator(conversation=self.conversation, patient_message="My new question"),
        )
        self.assertEqual(turns, EXPECTED_TURNS)

    def test_triage_sends_patient_message_once(self):
        turns = self._turns_sent_by(
            "agents.triage.agent",
            lambda: run_triage(conversation=self.conversation, patient_message="My new question"),
        )
        self.assertEqual(turns, EXPECTED_TURNS)

    def test_appointment_sends_patient_message_once(self):
        turns = self._turns_sent_by(
            "agents.appointment.agent",
            lambda: run_appointment_agent(
                conversation=self.conversation, patient=self.patient, patient_message="My new question"
            ),
        )
        self.assertEqual(turns, EXPECTED_TURNS)

    def test_follow_up_sends_patient_message_once(self):
        turns = self._turns_sent_by(
            "agents.follow_up.agent",
            lambda: run_follow_up_agent(
                conversation=self.conversation, patient=self.patient, patient_message="My new question"
            ),
        )
        self.assertEqual(turns, EXPECTED_TURNS)

    def test_repeated_identical_message_keeps_earlier_copy(self):
        # A patient who sends the same text twice in a row: only the
        # just-saved copy is dropped; the earlier turn stays in history.
        Message.objects.create(conversation=self.conversation, role="assistant", content="Answer two")
        Message.objects.create(conversation=self.conversation, role="user", content="My new question")
        turns = self._turns_sent_by(
            "agents.navigator.agent",
            lambda: run_navigator(conversation=self.conversation, patient_message="My new question"),
        )
        self.assertEqual(turns, EXPECTED_TURNS + [("assistant", "Answer two"), ("user", "My new question")])
