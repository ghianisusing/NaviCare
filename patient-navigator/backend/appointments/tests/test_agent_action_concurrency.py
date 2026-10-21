"""
Regression tests: an agent action is executed at most once, and only
while it is still fresh.
"""

from datetime import timedelta
from unittest import mock

from django.contrib.auth.models import User
from django.test import TransactionTestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient, APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from appointments import views as appointment_views
from appointments.models import AgentAction, Appointment, Availability, Department, Provider
from conversations.models import Conversation
from core.tests.concurrency import requires_postgres, run_concurrently
from patients.models import Patient


def _make_world(test):
    department = Department.objects.create(name="Dermatology")
    test.provider = Provider.objects.create(
        department=department, first_name="Lena", last_name="Ortiz", title="MD", active=True
    )
    start = (timezone.now() + timedelta(days=2)).replace(hour=10, minute=0, second=0, microsecond=0)
    Availability.objects.create(provider=test.provider, start_time=start, end_time=start + timedelta(hours=1))
    test.user = User.objects.create_user(username="confirm_twice", password="S0meStrongPass!")
    test.patient = Patient.objects.create(user=test.user, first_name="Cy", last_name="Twice")
    conversation = Conversation.objects.create(patient=test.patient)
    test.action = AgentAction.objects.create(
        patient=test.patient,
        conversation=conversation,
        tool_name="book_appointment",
        arguments={
            "provider_id": test.provider.id,
            "start_time": start.isoformat(),
            "end_time": (start + timedelta(minutes=30)).isoformat(),
        },
        status=AgentAction.Status.VALIDATED,
    )
    test.token = str(RefreshToken.for_user(test.user).access_token)


def _url(action, verb):
    return f"/api/appointments/agent-actions/{action.id}/{verb}/"


class AgentActionConfirmOnceTests(APITestCase):
    def setUp(self):
        _make_world(self)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token}")

    def test_new_actions_get_an_expiry(self):
        self.assertGreater(self.action.expires_at, timezone.now())

    def test_confirm_based_on_stale_read_does_not_execute_again(self):
        # The second request loaded the action while it was still VALIDATED...
        stale = AgentAction.objects.get(pk=self.action.pk)
        # ...and the first request then confirmed it.
        self.assertEqual(self.client.post(_url(self.action, "confirm")).status_code, status.HTTP_200_OK)

        with (
            mock.patch.object(AgentAction.objects, "get", return_value=stale),
            mock.patch.object(appointment_views, "_execute_agent_action", wraps=appointment_views._execute_agent_action) as execute,
        ):
            response = self.client.post(_url(self.action, "confirm"))

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        execute.assert_not_called()
        self.action.refresh_from_db()
        self.assertEqual(self.action.status, AgentAction.Status.EXECUTED)
        self.assertEqual(Appointment.objects.filter(patient=self.patient).count(), 1)

    def test_decline_based_on_stale_read_does_not_overwrite_confirm(self):
        stale = AgentAction.objects.get(pk=self.action.pk)
        self.client.post(_url(self.action, "confirm"))

        with mock.patch.object(AgentAction.objects, "get", return_value=stale):
            response = self.client.post(_url(self.action, "decline"))

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.action.refresh_from_db()
        self.assertEqual(self.action.status, AgentAction.Status.EXECUTED)

    def test_expired_action_cannot_be_confirmed(self):
        AgentAction.objects.filter(pk=self.action.pk).update(expires_at=timezone.now() - timedelta(seconds=1))

        response = self.client.post(_url(self.action, "confirm"))

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertIn("expired", response.data["error"])
        self.action.refresh_from_db()
        self.assertEqual(self.action.status, AgentAction.Status.EXPIRED)
        self.assertFalse(Appointment.objects.filter(patient=self.patient).exists())

    def test_unexpected_execution_error_marks_action_failed(self):
        with mock.patch.object(appointment_views, "_execute_agent_action", side_effect=RuntimeError("boom")):
            with self.assertLogs("django.request", level="ERROR"):
                response = self.client.post(_url(self.action, "confirm"))

        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.action.refresh_from_db()
        self.assertEqual(self.action.status, AgentAction.Status.FAILED)


@requires_postgres
class AgentActionConfirmRaceTests(TransactionTestCase):
    def setUp(self):
        _make_world(self)

    def test_concurrent_confirms_execute_once(self):
        def confirm():
            client = APIClient()
            client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token}")
            return client.post(_url(self.action, "confirm")).status_code

        outcomes = run_concurrently(confirm, confirm)

        self.assertEqual(sorted(outcomes), [status.HTTP_200_OK, status.HTTP_409_CONFLICT], outcomes)
        self.assertEqual(Appointment.objects.filter(patient=self.patient).count(), 1)
        self.action.refresh_from_db()
        self.assertEqual(self.action.status, AgentAction.Status.EXECUTED)
