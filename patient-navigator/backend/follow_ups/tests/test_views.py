from datetime import timedelta

from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from follow_ups.models import FollowUp, Reminder
from follow_ups.services import follow_up_service
from patients.models import Patient


class FollowUpApiTestCase(APITestCase):
    def setUp(self):
        self.user_a = User.objects.create_user(username="api_fu_a", password="S0meStrongPass!")
        self.patient_a = Patient.objects.create(user=self.user_a, first_name="A", last_name="Patient")
        self.user_b = User.objects.create_user(username="api_fu_b", password="S0meStrongPass!")
        self.patient_b = Patient.objects.create(user=self.user_b, first_name="B", last_name="Patient")

    def auth(self, user):
        token = RefreshToken.for_user(user).access_token
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")


class FollowUpEndpointTests(FollowUpApiTestCase):
    def test_create_follow_up(self):
        self.auth(self.user_a)
        response = self.client.post("/api/follow-ups/", {"title": "Contact clinic"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(FollowUp.objects.filter(patient=self.patient_a).count(), 1)

    def test_list_only_shows_own_follow_ups(self):
        follow_up_service.create_follow_up(patient=self.patient_b, title="B's task")
        self.auth(self.user_a)
        response = self.client.get("/api/follow-ups/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 0)

    def test_non_owner_cannot_view_follow_up(self):
        follow_up = follow_up_service.create_follow_up(patient=self.patient_a, title="A's task")
        self.auth(self.user_b)
        response = self.client.get(f"/api/follow-ups/{follow_up.id}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_owner_can_mark_complete_via_patch(self):
        follow_up = follow_up_service.create_follow_up(patient=self.patient_a, title="A's task")
        self.auth(self.user_a)
        response = self.client.patch(f"/api/follow-ups/{follow_up.id}/", {"status": "completed"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        follow_up.refresh_from_db()
        self.assertEqual(follow_up.status, "completed")

    def test_non_owner_cannot_complete(self):
        follow_up = follow_up_service.create_follow_up(patient=self.patient_a, title="A's task")
        self.auth(self.user_b)
        response = self.client.patch(f"/api/follow-ups/{follow_up.id}/", {"status": "completed"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        follow_up.refresh_from_db()
        self.assertEqual(follow_up.status, "pending")

    def test_delete_cancels_follow_up(self):
        follow_up = follow_up_service.create_follow_up(patient=self.patient_a, title="A's task")
        self.auth(self.user_a)
        response = self.client.delete(f"/api/follow-ups/{follow_up.id}/")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        follow_up.refresh_from_db()
        self.assertEqual(follow_up.status, "cancelled")

    def test_unauthenticated_rejected(self):
        response = self.client.get("/api/follow-ups/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class ReminderEndpointTests(FollowUpApiTestCase):
    def setUp(self):
        super().setUp()
        self.follow_up = follow_up_service.create_follow_up(patient=self.patient_a, title="A's task")

    def test_create_reminder(self):
        self.auth(self.user_a)
        scheduled_for = timezone.now() + timedelta(hours=2)
        response = self.client.post(
            "/api/reminders/", {"follow_up": self.follow_up.id, "scheduled_for": scheduled_for.isoformat()}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_non_owner_cannot_create_reminder_for_others_follow_up(self):
        self.auth(self.user_b)
        scheduled_for = timezone.now() + timedelta(hours=2)
        response = self.client.post(
            "/api/reminders/", {"follow_up": self.follow_up.id, "scheduled_for": scheduled_for.isoformat()}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_non_owner_cannot_cancel_reminder(self):
        reminder = follow_up_service.create_reminder(
            patient=self.patient_a, follow_up_id=self.follow_up.id, scheduled_for=timezone.now() + timedelta(hours=1)
        )
        self.auth(self.user_b)
        response = self.client.delete(f"/api/reminders/{reminder.id}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        reminder.refresh_from_db()
        self.assertEqual(reminder.status, "scheduled")

    def test_owner_can_cancel_reminder(self):
        reminder = follow_up_service.create_reminder(
            patient=self.patient_a, follow_up_id=self.follow_up.id, scheduled_for=timezone.now() + timedelta(hours=1)
        )
        self.auth(self.user_a)
        response = self.client.delete(f"/api/reminders/{reminder.id}/")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        reminder.refresh_from_db()
        self.assertEqual(reminder.status, "cancelled")

    def test_owner_can_reschedule_reminder(self):
        reminder = follow_up_service.create_reminder(
            patient=self.patient_a, follow_up_id=self.follow_up.id, scheduled_for=timezone.now() + timedelta(hours=1)
        )
        new_time = timezone.now() + timedelta(hours=5)
        self.auth(self.user_a)
        response = self.client.patch(f"/api/reminders/{reminder.id}/", {"scheduled_for": new_time.isoformat()}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class AppointmentReminderShortcutTests(FollowUpApiTestCase):
    def test_creates_follow_up_and_reminder_from_appointment(self):
        from appointments.models import Appointment, Department, Provider

        department = Department.objects.create(name="Dermatology")
        provider = Provider.objects.create(department=department, first_name="Alex", last_name="Rivera", active=True)
        appointment = Appointment.objects.create(
            patient=self.patient_a,
            provider=provider,
            start_time=timezone.now() + timedelta(days=2),
            end_time=timezone.now() + timedelta(days=2, minutes=30),
        )

        self.auth(self.user_a)
        response = self.client.post(
            "/api/follow-ups/appointment-reminder/", {"appointment": appointment.id, "hours_before": 24}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(FollowUp.objects.filter(patient=self.patient_a, appointment=appointment).count(), 1)
        self.assertEqual(Reminder.objects.filter(follow_up__appointment=appointment).count(), 1)

    def test_cannot_create_reminder_for_another_patients_appointment(self):
        from appointments.models import Appointment, Department, Provider

        department = Department.objects.create(name="Dermatology")
        provider = Provider.objects.create(department=department, first_name="Alex", last_name="Rivera", active=True)
        appointment = Appointment.objects.create(
            patient=self.patient_b,
            provider=provider,
            start_time=timezone.now() + timedelta(days=2),
            end_time=timezone.now() + timedelta(days=2, minutes=30),
        )

        self.auth(self.user_a)
        response = self.client.post(
            "/api/follow-ups/appointment-reminder/", {"appointment": appointment.id}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
