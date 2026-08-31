from datetime import timedelta

from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from appointments.models import AgentAction, Appointment, Availability, Department, Provider
from conversations.models import Conversation
from patients.models import Patient


class AgentActionConfirmDeclineTests(APITestCase):
    def setUp(self):
        self.department = Department.objects.create(name="Orthopedics")
        self.provider = Provider.objects.create(
            department=self.department, first_name="Samuel", last_name="Okafor", title="MD", active=True
        )
        start = (timezone.now() + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)
        Availability.objects.create(provider=self.provider, start_time=start, end_time=start + timedelta(hours=1))
        self.start = start
        self.end = start + timedelta(minutes=30)

        self.user_a = User.objects.create_user(username="agentaction_a", password="S0meStrongPass!")
        self.patient_a = Patient.objects.create(user=self.user_a, first_name="A", last_name="Patient")
        self.user_b = User.objects.create_user(username="agentaction_b", password="S0meStrongPass!")
        self.patient_b = Patient.objects.create(user=self.user_b, first_name="B", last_name="Patient")

        self.conversation = Conversation.objects.create(patient=self.patient_a)

        self.pending_booking = AgentAction.objects.create(
            patient=self.patient_a,
            conversation=self.conversation,
            agent="appointment",
            tool_name="book_appointment",
            arguments={
                "provider_id": self.provider.id,
                "start_time": self.start.isoformat(),
                "end_time": self.end.isoformat(),
            },
            status=AgentAction.Status.VALIDATED,
            result_summary=f"Book with Dr. Okafor at {self.start}",
        )

    def auth(self, user):
        token = RefreshToken.for_user(user).access_token
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def test_owner_can_confirm_pending_booking(self):
        self.auth(self.user_a)
        response = self.client.post(f"/api/appointments/agent-actions/{self.pending_booking.id}/confirm/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.pending_booking.refresh_from_db()
        self.assertEqual(self.pending_booking.status, AgentAction.Status.EXECUTED)
        self.assertTrue(Appointment.objects.filter(patient=self.patient_a, provider=self.provider).exists())

    def test_non_owner_cannot_confirm_pending_action(self):
        self.auth(self.user_b)
        response = self.client.post(f"/api/appointments/agent-actions/{self.pending_booking.id}/confirm/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.pending_booking.refresh_from_db()
        self.assertEqual(self.pending_booking.status, AgentAction.Status.VALIDATED)

    def test_owner_can_decline_pending_action(self):
        self.auth(self.user_a)
        response = self.client.post(f"/api/appointments/agent-actions/{self.pending_booking.id}/decline/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.pending_booking.refresh_from_db()
        self.assertEqual(self.pending_booking.status, AgentAction.Status.DECLINED)
        self.assertFalse(Appointment.objects.filter(patient=self.patient_a).exists())

    def test_confirming_already_executed_action_rejected(self):
        self.auth(self.user_a)
        self.client.post(f"/api/appointments/agent-actions/{self.pending_booking.id}/confirm/")
        response = self.client.post(f"/api/appointments/agent-actions/{self.pending_booking.id}/confirm/")
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)

    def test_confirming_action_with_now_unavailable_slot_fails_gracefully(self):
        # Someone else books the exact same slot before confirmation happens.
        Appointment.objects.create(
            patient=self.patient_b, provider=self.provider, start_time=self.start, end_time=self.end
        )
        self.auth(self.user_a)
        response = self.client.post(f"/api/appointments/agent-actions/{self.pending_booking.id}/confirm/")
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.pending_booking.refresh_from_db()
        self.assertEqual(self.pending_booking.status, AgentAction.Status.FAILED)
        # Only the one legitimate booking exists — no fabricated success.
        self.assertEqual(Appointment.objects.filter(provider=self.provider, start_time=self.start).count(), 1)

    def test_unauthenticated_cannot_confirm(self):
        response = self.client.post(f"/api/appointments/agent-actions/{self.pending_booking.id}/confirm/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_confirming_pending_cancel_action(self):
        appointment = Appointment.objects.create(
            patient=self.patient_a, provider=self.provider, start_time=self.start, end_time=self.end
        )
        cancel_action = AgentAction.objects.create(
            patient=self.patient_a,
            conversation=self.conversation,
            tool_name="cancel_appointment",
            arguments={"appointment_id": appointment.id},
            status=AgentAction.Status.VALIDATED,
        )
        self.auth(self.user_a)
        response = self.client.post(f"/api/appointments/agent-actions/{cancel_action.id}/confirm/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        appointment.refresh_from_db()
        self.assertEqual(appointment.status, "cancelled")
