"""
Runs agents/tests/eval_cases.py through the real Navigator routing
architecture.

Important caveat about what this does and doesn't prove: there is no
live LLM configured in this environment, so the Navigator's LLM call is
mocked to return the classification a correctly-behaving model *would*
produce for each input. That means this verifies the **routing and
safety architecture**, not the model's classification accuracy — which
is what Phase 6 asks for ("verify the architecture behaves safely," not
a live-model benchmark). Measuring real classification accuracy would
require running these same cases against a live model.

Emergency cases are the exception and are the strongest assertions
here: they run with no LLM mock at all, because that path is
deterministic and never calls the LLM.
"""

import json
from unittest import mock

from django.contrib.auth.models import User
from django.test import TestCase

from agents.core.llm import LLMResult
from agents.navigator import service as navigator_service
from conversations.models import Conversation
from patients.models import Patient

from .eval_cases import EVALUATION_CASES

# Maps each expected_route to the Navigator intent/action a
# well-behaved model would emit for that category.
ROUTE_TO_NAVIGATOR_OUTPUT = {
    "information": dict(intent="GENERAL_HEALTH_INFORMATION", recommended_action="ROUTE_TO_AGENT", target_agent="information"),
    "triage": dict(intent="SYMPTOM_CONCERN", recommended_action="ROUTE_TO_AGENT", target_agent="triage"),
    "appointment": dict(intent="APPOINTMENT_REQUEST", recommended_action="ROUTE_TO_AGENT", target_agent="appointment"),
    "follow_up": dict(intent="FOLLOW_UP_REQUEST", recommended_action="ROUTE_TO_AGENT", target_agent="follow_up"),
    "escalation": dict(intent="HUMAN_ASSISTANCE", recommended_action="ROUTE_TO_AGENT", target_agent="escalation"),
}


class FakeProvider:
    def __init__(self, text):
        self._text = text

    def complete(self, **kwargs):
        return LLMResult(text=self._text, raw={})


def _navigator_payload(**overrides):
    defaults = dict(
        urgency="normal",
        needs_clarification=False,
        clarifying_question=None,
        response="Let me help you with that.",
    )
    defaults.update(overrides)
    return json.dumps(defaults)


class EvaluationDatasetTests(TestCase):
    def setUp(self):
        user = User.objects.create_user(username="eval_patient", password="S0meStrongPass!")
        self.patient = Patient.objects.create(user=user, first_name="Eval", last_name="Patient")

    def test_dataset_is_well_formed(self):
        self.assertGreaterEqual(len(EVALUATION_CASES), 10)
        categories = {case["category"] for case in EVALUATION_CASES}
        self.assertIn("Emergency Detection", categories)
        self.assertIn("Escalation", categories)
        self.assertIn("Out-of-Scope Requests", categories)
        for case in EVALUATION_CASES:
            self.assertIn("input", case)
            self.assertIn("expected_route", case)
            self.assertIn("safety_requirement", case)

    def test_all_cases_route_correctly(self):
        for case in EVALUATION_CASES:
            with self.subTest(case=case["input"]):
                conversation = Conversation.objects.create(patient=self.patient)

                if case["expected_route"] == "emergency":
                    # Real deterministic pre-check, no LLM involved.
                    result = navigator_service.handle_patient_message(
                        conversation=conversation, patient_message=case["input"]
                    )
                    self.assertEqual(result.final_agent, "emergency")
                    self.assertEqual(result.display_urgency, "emergency")
                    continue

                payload = _navigator_payload(**ROUTE_TO_NAVIGATOR_OUTPUT[case["expected_route"]])

                with mock.patch("agents.navigator.agent.get_llm_provider", return_value=FakeProvider(payload)):
                    result = navigator_service.handle_patient_message(
                        conversation=conversation, patient_message=case["input"]
                    )

                self.assertEqual(result.final_agent, case["expected_route"], msg=f"case: {case['input']}")

    def test_every_case_produces_a_trace(self):
        from observability.models import AgentTrace

        conversation = Conversation.objects.create(patient=self.patient)
        payload = _navigator_payload(**ROUTE_TO_NAVIGATOR_OUTPUT["information"])

        with mock.patch("agents.navigator.agent.get_llm_provider", return_value=FakeProvider(payload)):
            result = navigator_service.handle_patient_message(
                conversation=conversation, patient_message="What is an MRI?"
            )

        self.assertTrue(AgentTrace.objects.filter(request_id=result.request_id).exists())
