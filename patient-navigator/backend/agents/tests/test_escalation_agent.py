from django.contrib.auth.models import User
from django.test import TestCase

from agents.escalation.agent import run_escalation_agent
from agents.escalation.schemas import derive_recommendation
from agents.escalation.service import handle_escalation_request
from conversations.models import Conversation
from escalations.models import Escalation
from patients.models import Patient


class DeriveRecommendationTests(TestCase):
    def test_human_assistance_intent_maps_to_patient_request(self):
        rec = derive_recommendation(intent="HUMAN_ASSISTANCE", urgency="normal")
        self.assertEqual(rec.reason, Escalation.Reason.PATIENT_REQUEST)
        self.assertEqual(rec.priority, Escalation.Priority.NORMAL)

    def test_urgent_non_human_request_maps_to_safety_review_with_high_priority(self):
        rec = derive_recommendation(intent="MEDICATION_INFORMATION", urgency="urgent")
        self.assertEqual(rec.reason, Escalation.Reason.SAFETY_REVIEW)
        self.assertEqual(rec.priority, Escalation.Priority.HIGH)

    def test_normal_non_human_request_maps_to_out_of_scope(self):
        rec = derive_recommendation(intent="GENERAL_NAVIGATION", urgency="normal")
        self.assertEqual(rec.reason, Escalation.Reason.OUT_OF_SCOPE)
        self.assertEqual(rec.priority, Escalation.Priority.NORMAL)

    def test_reason_is_always_a_valid_choice(self):
        # The LLM never supplies a reason string directly — this asserts
        # every derivable combination lands inside the controlled set.
        for intent in ["HUMAN_ASSISTANCE", "MEDICATION_INFORMATION", "GENERAL_NAVIGATION", "UNKNOWN"]:
            for urgency in ["normal", "urgent", "unknown"]:
                rec = derive_recommendation(intent=intent, urgency=urgency)
                self.assertIn(rec.reason, Escalation.Reason.values)
                self.assertIn(rec.priority, Escalation.Priority.values)


class RunEscalationAgentTests(TestCase):
    def test_returns_fixed_non_empty_response(self):
        result = run_escalation_agent(intent="HUMAN_ASSISTANCE", urgency="normal")
        self.assertTrue(result.response.strip())
        self.assertEqual(result.reason, Escalation.Reason.PATIENT_REQUEST)


class HandleEscalationRequestTests(TestCase):
    def setUp(self):
        user = User.objects.create_user(username="esc_agent_patient", password="S0meStrongPass!")
        self.patient = Patient.objects.create(user=user, first_name="Esc", last_name="Agent")
        self.conversation = Conversation.objects.create(patient=self.patient)

    def test_creates_a_real_escalation(self):
        result = handle_escalation_request(
            conversation=self.conversation, patient=self.patient, intent="HUMAN_ASSISTANCE", urgency="normal"
        )
        self.assertTrue(result.succeeded)
        self.assertIsNotNone(result.escalation_id)
        self.assertTrue(Escalation.objects.filter(id=result.escalation_id, patient=self.patient).exists())

    def test_repeated_calls_are_idempotent_for_open_conversation(self):
        first = handle_escalation_request(
            conversation=self.conversation, patient=self.patient, intent="HUMAN_ASSISTANCE", urgency="normal"
        )
        second = handle_escalation_request(
            conversation=self.conversation, patient=self.patient, intent="HUMAN_ASSISTANCE", urgency="normal"
        )
        self.assertEqual(first.escalation_id, second.escalation_id)

    def test_response_never_leaks_internal_reason_codes(self):
        result = handle_escalation_request(
            conversation=self.conversation, patient=self.patient, intent="GENERAL_NAVIGATION", urgency="normal"
        )
        self.assertNotIn("out_of_scope", result.response_text)
        self.assertNotIn("OUT_OF_SCOPE", result.response_text)
