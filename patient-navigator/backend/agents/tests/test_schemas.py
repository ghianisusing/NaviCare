import json

from django.test import SimpleTestCase

from agents.core.exceptions import InvalidAgentOutputError
from agents.navigator.schemas import parse_agent_output


VALID_PAYLOAD = {
    "intent": "GENERAL_NAVIGATION",
    "urgency": "normal",
    "needs_clarification": True,
    "clarifying_question": "What type of healthcare service are you looking for?",
    "recommended_action": "ASK_CLARIFYING_QUESTION",
    "target_agent": None,
    "response": "I can help you figure out which healthcare service you need.",
}


class ParseAgentOutputTests(SimpleTestCase):
    def test_valid_payload_parses(self):
        output = parse_agent_output(json.dumps(VALID_PAYLOAD))
        self.assertEqual(output.intent, "GENERAL_NAVIGATION")
        self.assertEqual(output.urgency, "normal")
        self.assertTrue(output.needs_clarification)
        self.assertEqual(output.target_agent, None)

    def test_payload_wrapped_in_prose_is_extracted(self):
        wrapped = f"Sure, here you go:\n```json\n{json.dumps(VALID_PAYLOAD)}\n```\nLet me know if that helps."
        output = parse_agent_output(wrapped)
        self.assertEqual(output.intent, "GENERAL_NAVIGATION")

    def test_unknown_intent_rejected(self):
        payload = {**VALID_PAYLOAD, "intent": "DIAGNOSE_PATIENT"}
        with self.assertRaises(InvalidAgentOutputError):
            parse_agent_output(json.dumps(payload))

    def test_unknown_urgency_rejected(self):
        payload = {**VALID_PAYLOAD, "urgency": "super-urgent"}
        with self.assertRaises(InvalidAgentOutputError):
            parse_agent_output(json.dumps(payload))

    def test_unknown_target_agent_rejected(self):
        payload = {**VALID_PAYLOAD, "target_agent": "diagnosis"}
        with self.assertRaises(InvalidAgentOutputError):
            parse_agent_output(json.dumps(payload))

    def test_unknown_recommended_action_rejected(self):
        payload = {**VALID_PAYLOAD, "recommended_action": "PRESCRIBE_MEDICATION"}
        with self.assertRaises(InvalidAgentOutputError):
            parse_agent_output(json.dumps(payload))

    def test_needs_clarification_without_question_rejected(self):
        payload = {**VALID_PAYLOAD, "needs_clarification": True, "clarifying_question": None}
        with self.assertRaises(InvalidAgentOutputError):
            parse_agent_output(json.dumps(payload))

    def test_empty_response_rejected(self):
        payload = {**VALID_PAYLOAD, "response": "   "}
        with self.assertRaises(InvalidAgentOutputError):
            parse_agent_output(json.dumps(payload))

    def test_malformed_json_rejected(self):
        with self.assertRaises(InvalidAgentOutputError):
            parse_agent_output("not json at all")

    def test_valid_target_agent_accepted(self):
        payload = {
            **VALID_PAYLOAD,
            "needs_clarification": False,
            "clarifying_question": None,
            "recommended_action": "ROUTE_TO_AGENT",
            "target_agent": "appointment",
        }
        output = parse_agent_output(json.dumps(payload))
        self.assertEqual(output.target_agent, "appointment")
