import json

from django.test import SimpleTestCase

from agents.core.exceptions import InvalidAgentOutputError
from agents.information.schemas import parse_information_output


class ParseInformationOutputTests(SimpleTestCase):
    def test_valid_payload_parses(self):
        payload = json.dumps({"response": "A blood test measures...", "has_sufficient_information": True})
        response, sufficient = parse_information_output(payload)
        self.assertEqual(response, "A blood test measures...")
        self.assertTrue(sufficient)

    def test_insufficient_information_flag_parses(self):
        payload = json.dumps({"response": "I don't have enough information.", "has_sufficient_information": False})
        response, sufficient = parse_information_output(payload)
        self.assertFalse(sufficient)

    def test_missing_field_rejected(self):
        payload = json.dumps({"response": "Some answer"})
        with self.assertRaises(InvalidAgentOutputError):
            parse_information_output(payload)

    def test_non_boolean_flag_rejected(self):
        payload = json.dumps({"response": "Some answer", "has_sufficient_information": "yes"})
        with self.assertRaises(InvalidAgentOutputError):
            parse_information_output(payload)

    def test_empty_response_rejected(self):
        payload = json.dumps({"response": "   ", "has_sufficient_information": True})
        with self.assertRaises(InvalidAgentOutputError):
            parse_information_output(payload)

    def test_malformed_json_rejected(self):
        with self.assertRaises(InvalidAgentOutputError):
            parse_information_output("not json")
