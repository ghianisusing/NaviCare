"""
Regression tests: once a staff member owns a conversation (escalation
ASSIGNED or IN_PROGRESS), the AI must not answer the patient. The
deterministic emergency pre-check still runs first.
"""

from unittest import mock

from django.contrib.auth.models import User
from django.test import TestCase

from agents.navigator import safety
from agents.navigator import service as navigator_service
from agents.tests.test_navigator_service import FakeProvider, _payload
from conversations.models import Conversation
from escalations.models import Escalation, EscalationEvent
from escalations.services import escalation_service
from observability.models import AgentTrace
from patients.models import Patient


class HumanHandoffTests(TestCase):
    def setUp(self):
        user = User.objects.create_user(username="handoff", password="S0meStrongPass!")
        self.patient = Patient.objects.create(user=user, first_name="Hal", last_name="Doe")
        self.conversation = Conversation.objects.create(patient=self.patient)
        self.staff = User.objects.create_user(username="handoff_staff", password="S0meStrongPass!", is_staff=True)
        self.escalation = escalation_service.create_escalation(
            patient=self.patient, conversation=self.conversation, reason=Escalation.Reason.PATIENT_REQUEST
        )
        self.provider = FakeProvider(text=_payload())
        patcher = mock.patch("agents.navigator.agent.get_llm_provider", return_value=self.provider)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _send(self, text="Any update on my request?"):
        return navigator_service.handle_patient_message(conversation=self.conversation, patient_message=text)

    def _assert_ai_stayed_silent(self, result):
        self.assertEqual(self.provider.calls, 0)
        self.assertEqual(result.response_text, navigator_service.HUMAN_HANDOFF_RESPONSE)
        self.assertEqual(result.final_agent, "human")
        self.assertEqual(result.escalation_id, self.escalation.id)
        self.assertTrue(
            EscalationEvent.objects.filter(
                escalation=self.escalation, action=EscalationEvent.Action.PATIENT_MESSAGE_RECEIVED
            ).exists()
        )

    def test_assigned_escalation_skips_the_llm_and_notifies_staff(self):
        escalation_service.assign_escalation(staff_user=self.staff, escalation_id=self.escalation.id)
        self._assert_ai_stayed_silent(self._send())

    def test_in_progress_escalation_skips_the_llm_and_notifies_staff(self):
        escalation_service.send_staff_response(
            staff_user=self.staff, escalation_id=self.escalation.id, content="Hi, I'm looking into this."
        )
        self._assert_ai_stayed_silent(self._send())

    def test_handoff_turn_trace_is_finished(self):
        escalation_service.assign_escalation(staff_user=self.staff, escalation_id=self.escalation.id)
        result = self._send()
        trace = AgentTrace.objects.get(request_id=result.request_id)
        self.assertEqual(trace.status, "completed")
        self.assertEqual(trace.final_agent, "human")

    def test_pending_escalation_still_gets_ai_help(self):
        result = self._send()
        self.assertEqual(self.provider.calls, 1)
        self.assertNotEqual(result.response_text, navigator_service.HUMAN_HANDOFF_RESPONSE)

    def test_resolved_escalation_returns_conversation_to_ai(self):
        escalation_service.assign_escalation(staff_user=self.staff, escalation_id=self.escalation.id)
        escalation_service.resolve_escalation(staff_user=self.staff, escalation_id=self.escalation.id)
        self._send()
        self.assertEqual(self.provider.calls, 1)

    def test_emergency_pre_check_still_runs_during_handoff(self):
        escalation_service.assign_escalation(staff_user=self.staff, escalation_id=self.escalation.id)
        result = self._send("I have crushing chest pain and can't breathe")
        self.assertEqual(result.response_text, safety.SAFETY_RESPONSE)
        self.assertEqual(result.display_urgency, "emergency")
        self.assertEqual(self.provider.calls, 0)
