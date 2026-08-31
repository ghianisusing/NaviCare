import datetime as dt

from django.test import SimpleTestCase, TestCase

from tools.exceptions import InvalidToolArgumentsError, ToolNotFoundError
from tools.registry import get_tool, list_tools
from tools.schemas import ToolField, ToolSpec, validate_arguments

# Importing appointment_tools registers the real tools with the shared
# registry as a side effect — needed for get_tool()/list_tools() below
# to see anything.
import tools.appointment_tools  # noqa: F401


class RegistryTests(SimpleTestCase):
    def test_known_tool_is_retrievable(self):
        spec = get_tool("search_departments")
        self.assertEqual(spec.name, "search_departments")

    def test_unknown_tool_rejected(self):
        with self.assertRaises(ToolNotFoundError):
            get_tool("delete_patient")

    def test_all_expected_tools_registered(self):
        names = {spec.name for spec in list_tools()}
        expected = {
            "search_departments",
            "search_providers",
            "find_available_slots",
            "get_patient_appointments",
            "book_appointment",
            "cancel_appointment",
            "reschedule_appointment",
        }
        self.assertEqual(expected, expected & names)

    def test_mutating_tools_require_confirmation(self):
        for name in ("book_appointment", "cancel_appointment", "reschedule_appointment"):
            self.assertTrue(get_tool(name).requires_confirmation)

    def test_read_only_tools_do_not_require_confirmation(self):
        for name in ("search_departments", "search_providers", "find_available_slots", "get_patient_appointments"):
            self.assertFalse(get_tool(name).requires_confirmation)


class ValidateArgumentsTests(SimpleTestCase):
    def setUp(self):
        self.spec = ToolSpec(
            name="example_tool",
            description="test",
            fields=[
                ToolField("name", "str"),
                ToolField("count", "int", required=False),
                ToolField("status", "str", required=False, allowed_values=("a", "b")),
                ToolField("when", "date", required=False),
            ],
            requires_confirmation=False,
            handler=lambda patient, **kwargs: kwargs,
        )

    def test_valid_arguments_pass(self):
        result = validate_arguments(self.spec, {"name": "hello", "count": 3})
        self.assertEqual(result["name"], "hello")
        self.assertEqual(result["count"], 3)

    def test_missing_required_field_rejected(self):
        with self.assertRaises(InvalidToolArgumentsError):
            validate_arguments(self.spec, {"count": 3})

    def test_unknown_field_rejected(self):
        with self.assertRaises(InvalidToolArgumentsError):
            validate_arguments(self.spec, {"name": "hi", "unexpected": "field"})

    def test_wrong_type_rejected(self):
        with self.assertRaises(InvalidToolArgumentsError):
            validate_arguments(self.spec, {"name": "hi", "count": "not a number"})

    def test_disallowed_value_rejected(self):
        with self.assertRaises(InvalidToolArgumentsError):
            validate_arguments(self.spec, {"name": "hi", "status": "z"})

    def test_allowed_value_accepted(self):
        result = validate_arguments(self.spec, {"name": "hi", "status": "a"})
        self.assertEqual(result["status"], "a")

    def test_date_field_coerced(self):
        result = validate_arguments(self.spec, {"name": "hi", "when": "2026-09-01"})
        self.assertEqual(result["when"], dt.date(2026, 9, 1))

    def test_invalid_date_rejected(self):
        with self.assertRaises(InvalidToolArgumentsError):
            validate_arguments(self.spec, {"name": "hi", "when": "not-a-date"})

    def test_non_dict_arguments_rejected(self):
        with self.assertRaises(InvalidToolArgumentsError):
            validate_arguments(self.spec, "not a dict")

    def test_optional_field_omitted_is_fine(self):
        result = validate_arguments(self.spec, {"name": "hi"})
        self.assertNotIn("count", result)


class ExecuteToolIntegrationTests(TestCase):
    """Exercises the full registry -> validation -> real handler path
    against the actual appointment_service, using an in-memory search
    (read-only, no DB side effects)."""

    def test_search_departments_end_to_end(self):
        from django.contrib.auth.models import User

        from appointments.models import Department
        from patients.models import Patient
        from tools.registry import execute_tool

        Department.objects.create(name="Neurology")
        user = User.objects.create_user(username="toolsuser", password="S0meStrongPass!")
        patient = Patient.objects.create(user=user, first_name="Tool", last_name="User")

        result = execute_tool("search_departments", patient=patient, raw_arguments={"query": "Neuro"})
        names = [d["name"] for d in result["departments"]]
        self.assertIn("Neurology", names)

    def test_execute_unknown_tool_rejected(self):
        from django.contrib.auth.models import User

        from patients.models import Patient
        from tools.registry import execute_tool

        user = User.objects.create_user(username="toolsuser2", password="S0meStrongPass!")
        patient = Patient.objects.create(user=user, first_name="Tool", last_name="User")

        with self.assertRaises(ToolNotFoundError):
            execute_tool("delete_patient", patient=patient, raw_arguments={})
