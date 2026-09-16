from django.test import SimpleTestCase

from agents.core.exceptions import InvalidAgentOutputError, LLMResponseError, LLMUnavailableError
from observability.errors import classify_exception
from tools.exceptions import InvalidToolArgumentsError, ToolAuthorizationError, ToolError, ToolNotFoundError


class ClassifyExceptionTests(SimpleTestCase):
    def test_llm_unavailable_classified_as_timeout(self):
        self.assertEqual(classify_exception(LLMUnavailableError("down")), "timeout")

    def test_llm_response_error_classified_as_llm_error(self):
        self.assertEqual(classify_exception(LLMResponseError("bad")), "llm_error")

    def test_invalid_agent_output_classified_as_validation_error(self):
        self.assertEqual(classify_exception(InvalidAgentOutputError("bad json")), "validation_error")

    def test_tool_authorization_error_classified_as_authorization_error(self):
        self.assertEqual(classify_exception(ToolAuthorizationError("nope")), "authorization_error")

    def test_tool_not_found_classified_as_validation_error(self):
        self.assertEqual(classify_exception(ToolNotFoundError("unknown")), "validation_error")

    def test_invalid_tool_arguments_classified_as_validation_error(self):
        self.assertEqual(classify_exception(InvalidToolArgumentsError("bad args")), "validation_error")

    def test_generic_tool_error_classified_as_tool_error(self):
        self.assertEqual(classify_exception(ToolError("failed")), "tool_error")

    def test_unknown_exception_classified_as_unknown_error(self):
        self.assertEqual(classify_exception(RuntimeError("mystery")), "unknown_error")

    def test_permission_error_classified_as_authorization_error(self):
        self.assertEqual(classify_exception(PermissionError("denied")), "authorization_error")

    def test_timeout_error_classified_as_timeout(self):
        self.assertEqual(classify_exception(TimeoutError("too slow")), "timeout")
