import json

from django.test import SimpleTestCase

from agents.core.exceptions import InvalidAgentOutputError
from agents.appointment.schemas import parse_appointment_output

VALID_SEARCH_PAYLOAD = {
    "action": "FIND_AVAILABLE_SLOTS",
    "needs_clarification": False,
    "clarifying_question": None,
    "tool": "find_available_slots",
    "arguments": {"department_name": "Dermatology"},
    "response": "Let me find some dermatology appointments for you.",
}


class ParseAppointmentOutputTests(SimpleTestCase):
    def test_valid_search_payload_parses(self):
        output = parse_appointment_output(json.dumps(VALID_SEARCH_PAYLOAD))
        self.assertEqual(output.action, "FIND_AVAILABLE_SLOTS")
        self.assertEqual(output.tool, "find_available_slots")

    def test_unknown_action_rejected(self):
        payload = {**VALID_SEARCH_PAYLOAD, "action": "DELETE_PATIENT_RECORD"}
        with self.assertRaises(InvalidAgentOutputError):
            parse_appointment_output(json.dumps(payload))

    def test_clarification_payload_parses(self):
        payload = {
            "action": "ASK_CLARIFYING_QUESTION",
            "needs_clarification": True,
            "clarifying_question": "What department are you looking for?",
            "tool": None,
            "arguments": {},
            "response": "What department are you looking for?",
        }
        output = parse_appointment_output(json.dumps(payload))
        self.assertTrue(output.needs_clarification)
        self.assertIsNone(output.tool)

    def test_needs_clarification_without_question_rejected(self):
        payload = {**VALID_SEARCH_PAYLOAD, "needs_clarification": True, "clarifying_question": None}
        with self.assertRaises(InvalidAgentOutputError):
            parse_appointment_output(json.dumps(payload))

    def test_mismatched_tool_for_action_rejected(self):
        payload = {**VALID_SEARCH_PAYLOAD, "tool": "book_appointment"}
        with self.assertRaises(InvalidAgentOutputError):
            parse_appointment_output(json.dumps(payload))

    def test_tool_not_in_allowlist_rejected(self):
        payload = {
            "action": "RESPOND",
            "needs_clarification": False,
            "clarifying_question": None,
            "tool": "delete_everything",
            "arguments": {},
            "response": "Sure!",
        }
        with self.assertRaises(InvalidAgentOutputError):
            parse_appointment_output(json.dumps(payload))

    def test_respond_action_with_no_tool_parses(self):
        payload = {
            "action": "RESPOND",
            "needs_clarification": False,
            "clarifying_question": None,
            "tool": None,
            "arguments": {},
            "response": "I can help you with appointments — what would you like to do?",
        }
        output = parse_appointment_output(json.dumps(payload))
        self.assertIsNone(output.tool)

    def test_book_appointment_payload_parses(self):
        payload = {
            "action": "BOOK_APPOINTMENT",
            "needs_clarification": False,
            "clarifying_question": None,
            "tool": "book_appointment",
            "arguments": {
                "provider_id": 3,
                "start_time": "2026-09-03T10:00:00",
                "end_time": "2026-09-03T10:30:00",
            },
            "response": "You're about to book with Dr. Smith on September 3 at 10:00 AM.",
        }
        output = parse_appointment_output(json.dumps(payload))
        self.assertEqual(output.action, "BOOK_APPOINTMENT")
        self.assertEqual(output.arguments["provider_id"], 3)

    def test_empty_response_rejected(self):
        payload = {**VALID_SEARCH_PAYLOAD, "response": "   "}
        with self.assertRaises(InvalidAgentOutputError):
            parse_appointment_output(json.dumps(payload))

    def test_malformed_json_rejected(self):
        with self.assertRaises(InvalidAgentOutputError):
            parse_appointment_output("not json")
