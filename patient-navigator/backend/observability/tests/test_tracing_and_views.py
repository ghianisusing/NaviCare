from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from conversations.models import Conversation
from observability.tracing import Tracer
from patients.models import Patient


class ObservabilityApiTestCase(APITestCase):
    def setUp(self):
        self.patient_user = User.objects.create_user(username="obs_patient", password="S0meStrongPass!")
        self.patient = Patient.objects.create(user=self.patient_user, first_name="A", last_name="Patient")
        self.conversation = Conversation.objects.create(patient=self.patient)

        self.staff_user = User.objects.create_user(username="obs_staff", password="S0meStrongPass!", is_staff=True)
        self.admin_user = User.objects.create_user(
            username="obs_admin", password="S0meStrongPass!", is_staff=True, is_superuser=True
        )

        tracer = Tracer(conversation=self.conversation, patient=self.patient)
        with tracer.step("navigator", "classify_intent") as step:
            step.metadata["intent"] = "GENERAL_HEALTH_INFORMATION"
        tracer.finish(status="completed", final_agent="information")
        self.trace = tracer.trace

    def auth(self, user):
        token = RefreshToken.for_user(user).access_token
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")


class ObservabilityRbacTests(ObservabilityApiTestCase):
    def test_patient_cannot_list_traces(self):
        self.auth(self.patient_user)
        response = self.client.get("/api/agent-traces/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_patient_cannot_view_trace_detail(self):
        self.auth(self.patient_user)
        response = self.client.get(f"/api/agent-traces/{self.trace.id}/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_patient_cannot_view_metrics(self):
        self.auth(self.patient_user)
        response = self.client.get("/api/agent-metrics/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_care_coordinator_staff_cannot_view_traces(self):
        # A plain is_staff user (care coordinator) is not automatically
        # a system admin — traces/metrics are superuser-only.
        self.auth(self.staff_user)
        response = self.client.get("/api/agent-traces/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_care_coordinator_staff_cannot_view_metrics(self):
        self.auth(self.staff_user)
        response = self.client.get("/api/agent-metrics/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_unauthenticated_cannot_view_traces(self):
        response = self.client.get("/api/agent-traces/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_admin_can_list_traces(self):
        self.auth(self.admin_user)
        response = self.client.get("/api/agent-traces/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_admin_can_view_trace_detail_with_steps(self):
        self.auth(self.admin_user)
        response = self.client.get(f"/api/agent-traces/{self.trace.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["steps"]), 1)
        self.assertEqual(response.data["steps"][0]["metadata"]["intent"], "GENERAL_HEALTH_INFORMATION")

    def test_admin_can_view_metrics(self):
        self.auth(self.admin_user)
        response = self.client.get("/api/agent-metrics/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["agent_executions"], 1)
        self.assertEqual(response.data["successful_executions"], 1)

    def test_metrics_include_expected_keys(self):
        self.auth(self.admin_user)
        response = self.client.get("/api/agent-metrics/")
        for key in (
            "total_conversations",
            "agent_executions",
            "successful_executions",
            "failed_executions",
            "escalations",
            "tool_calls",
            "tool_failures",
            "avg_latency_ms",
            "executions_by_agent",
            "failures_by_error_type",
        ):
            self.assertIn(key, response.data)


class TracerBehaviorTests(ObservabilityApiTestCase):
    def test_failed_step_marks_trace_step_failed_and_reraises(self):
        tracer = Tracer(conversation=self.conversation, patient=self.patient)
        with self.assertRaises(ValueError):
            with tracer.step("navigator", "classify_intent"):
                raise ValueError("boom")

        step = tracer.trace.steps.get(step_index=1)
        self.assertEqual(step.status, "failed")
        self.assertEqual(step.metadata["error_type"], "unknown_error")

    def test_trace_records_total_latency(self):
        tracer = Tracer(conversation=self.conversation, patient=self.patient)
        with tracer.step("navigator", "classify_intent"):
            pass
        tracer.finish(status="completed", final_agent="navigator")
        self.assertIsNotNone(tracer.trace.total_latency_ms)
        self.assertGreaterEqual(tracer.trace.total_latency_ms, 0)

    def test_each_trace_has_unique_request_id(self):
        tracer_a = Tracer(conversation=self.conversation, patient=self.patient)
        tracer_b = Tracer(conversation=self.conversation, patient=self.patient)
        self.assertNotEqual(tracer_a.request_id, tracer_b.request_id)

    def test_steps_are_indexed_in_order(self):
        tracer = Tracer(conversation=self.conversation, patient=self.patient)
        with tracer.step("safety", "evaluate_rules"):
            pass
        with tracer.step("navigator", "classify_intent"):
            pass
        indices = list(tracer.trace.steps.values_list("step_index", flat=True))
        self.assertEqual(indices, [1, 2])
