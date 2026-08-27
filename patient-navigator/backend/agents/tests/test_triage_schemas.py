import json

from django.test import SimpleTestCase

from agents.core.exceptions import InvalidAgentOutputError
from agents.triage.schemas import parse_triage_output

VALID_PAYLOAD = {
    "urgency": "routine",
    "warning_signs": [],
    "needs_clarification": True,
    "clarifying_question": "How long have you had this cough?",
    "recommended_action": "ASK_CLARIFYING_QUESTION",
    "confidence": 0.7,
    "response": "How long have you had this cough?",
}


class ParseTriageOutputTests(SimpleTestCase):
    def test_valid_payload_parses(self):
        output = parse_triage_output(json.dumps(VALID_PAYLOAD))
        self.assertEqual(output.urgency, "routine")
        self.assertTrue(output.needs_clarification)
        self.assertEqual(output.confidence, 0.7)

    def test_unknown_urgency_rejected(self):
        payload = {**VALID_PAYLOAD, "urgency": "critical"}
        with self.assertRaises(InvalidAgentOutputError):
            parse_triage_output(json.dumps(payload))

    def test_unknown_recommended_action_rejected(self):
        payload = {**VALID_PAYLOAD, "recommended_action": "PRESCRIBE_MEDICATION"}
        with self.assertRaises(InvalidAgentOutputError):
            parse_triage_output(json.dumps(payload))

    def test_confidence_out_of_range_rejected(self):
        payload = {**VALID_PAYLOAD, "confidence": 1.5}
        with self.assertRaises(InvalidAgentOutputError):
            parse_triage_output(json.dumps(payload))

    def test_confidence_non_numeric_rejected(self):
        payload = {**VALID_PAYLOAD, "confidence": "high"}
        with self.assertRaises(InvalidAgentOutputError):
            parse_triage_output(json.dumps(payload))

    def test_warning_signs_must_be_list_of_strings(self):
        payload = {**VALID_PAYLOAD, "warning_signs": "difficulty breathing"}
        with self.assertRaises(InvalidAgentOutputError):
            parse_triage_output(json.dumps(payload))

    def test_needs_clarification_without_question_rejected(self):
        payload = {**VALID_PAYLOAD, "needs_clarification": True, "clarifying_question": None}
        with self.assertRaises(InvalidAgentOutputError):
            parse_triage_output(json.dumps(payload))

    def test_valid_emergency_payload(self):
        payload = {
            "urgency": "emergency",
            "warning_signs": ["chest pain", "difficulty breathing"],
            "needs_clarification": False,
            "clarifying_question": None,
            "recommended_action": "SEEK_EMERGENCY_CARE",
            "confidence": 0.95,
            "response": "Please seek immediate medical attention.",
        }
        output = parse_triage_output(json.dumps(payload))
        self.assertEqual(output.urgency, "emergency")
        self.assertEqual(output.warning_signs, ["chest pain", "difficulty breathing"])
