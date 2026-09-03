import json

from django.test import SimpleTestCase

from agents.core.exceptions import InvalidAgentOutputError
from agents.follow_up.schemas import parse_follow_up_output

VALID_PAYLOAD = {
    "action": "GET_REMINDERS",
    "needs_clarification": False,
    "clarifying_question": None,
    "tool": "get_reminders",
    "arguments": {},
    "response": "Here are your reminders.",
}


class ParseFollowUpOutputTests(SimpleTestCase):
    def test_valid_payload_parses(self):
        output = parse_follow_up_output(json.dumps(VALID_PAYLOAD))
        self.assertEqual(output.action, "GET_REMINDERS")
        self.assertEqual(output.tool, "get_reminders")

    def test_unknown_action_rejected(self):
        payload = {**VALID_PAYLOAD, "action": "DELETE_ACCOUNT"}
        with self.assertRaises(InvalidAgentOutputError):
            parse_follow_up_output(json.dumps(payload))

    def test_clarification_requires_question(self):
        payload = {**VALID_PAYLOAD, "needs_clarification": True, "clarifying_question": None}
        with self.assertRaises(InvalidAgentOutputError):
            parse_follow_up_output(json.dumps(payload))

    def test_mismatched_tool_rejected(self):
        payload = {**VALID_PAYLOAD, "tool": "cancel_reminder"}
        with self.assertRaises(InvalidAgentOutputError):
            parse_follow_up_output(json.dumps(payload))

    def test_create_reminder_payload_parses(self):
        payload = {
            "action": "CREATE_REMINDER",
            "needs_clarification": False,
            "clarifying_question": None,
            "tool": "create_reminder",
            "arguments": {"follow_up_id": 5, "scheduled_for": "2026-09-03T10:00:00+00:00"},
            "response": "I'll remind you then.",
        }
        output = parse_follow_up_output(json.dumps(payload))
        self.assertEqual(output.arguments["follow_up_id"], 5)

    def test_unknown_tool_rejected(self):
        payload = {
            "action": "RESPOND",
            "needs_clarification": False,
            "clarifying_question": None,
            "tool": "delete_all_reminders",
            "arguments": {},
            "response": "Sure!",
        }
        with self.assertRaises(InvalidAgentOutputError):
            parse_follow_up_output(json.dumps(payload))

    def test_empty_response_rejected(self):
        payload = {**VALID_PAYLOAD, "response": "  "}
        with self.assertRaises(InvalidAgentOutputError):
            parse_follow_up_output(json.dumps(payload))

    def test_malformed_json_rejected(self):
        with self.assertRaises(InvalidAgentOutputError):
            parse_follow_up_output("not json")
