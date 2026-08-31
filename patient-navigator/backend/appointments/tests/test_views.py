from datetime import timedelta

from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken
from django.utils import timezone

from appointments.models import Appointment, Availability, Department, Provider
from patients.models import Patient


class AppointmentApiTestCase(APITestCase):
    def setUp(self):
        self.department = Department.objects.create(name="Pediatrics")
        self.provider = Provider.objects.create(
            department=self.department, first_name="Jordan", last_name="Lee", title="MD", active=True
        )
        start = (timezone.now() + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)
        Availability.objects.create(provider=self.provider, start_time=start, end_time=start + timedelta(hours=2))
        self.start = start
        self.end = start + timedelta(minutes=30)

        self.user_a = User.objects.create_user(username="api_patient_a", password="S0meStrongPass!")
        self.patient_a = Patient.objects.create(user=self.user_a, first_name="A", last_name="Patient")
        self.user_b = User.objects.create_user(username="api_patient_b", password="S0meStrongPass!")
        self.patient_b = Patient.objects.create(user=self.user_b, first_name="B", last_name="Patient")

    def auth(self, user):
        token = RefreshToken.for_user(user).access_token
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")


class DepartmentProviderListTests(AppointmentApiTestCase):
    def test_list_departments_requires_auth(self):
        response = self.client.get("/api/departments/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_authenticated_patient_can_list_departments(self):
        self.auth(self.user_a)
        response = self.client.get("/api/departments/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(any(d["name"] == "Pediatrics" for d in response.data))

    def test_authenticated_patient_can_list_providers(self):
        self.auth(self.user_a)
        response = self.client.get("/api/providers/?department=Pediatrics")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_available_slots_endpoint(self):
        self.auth(self.user_a)
        response = self.client.get("/api/appointments/available-slots/?department=Pediatrics")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreater(len(response.data), 0)


class DirectBookingApiTests(AppointmentApiTestCase):
    def test_book_appointment_directly(self):
        self.auth(self.user_a)
        response = self.client.post(
            "/api/appointments/",
            {
                "provider": self.provider.id,
                "start_time": self.start.isoformat(),
                "end_time": self.end.isoformat(),
                "reason": "Checkup",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Appointment.objects.filter(patient=self.patient_a).count(), 1)

    def test_double_booking_via_api_returns_conflict(self):
        self.auth(self.user_a)
        self.client.post(
            "/api/appointments/",
            {"provider": self.provider.id, "start_time": self.start.isoformat(), "end_time": self.end.isoformat()},
            format="json",
        )
        self.auth(self.user_b)
        response = self.client.post(
            "/api/appointments/",
            {"provider": self.provider.id, "start_time": self.start.isoformat(), "end_time": self.end.isoformat()},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)

    def test_list_only_shows_own_appointments(self):
        Appointment.objects.create(
            patient=self.patient_b, provider=self.provider, start_time=self.start, end_time=self.end
        )
        self.auth(self.user_a)
        response = self.client.get("/api/appointments/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 0)


class AppointmentAuthorizationTests(AppointmentApiTestCase):
    def setUp(self):
        super().setUp()
        self.appointment = Appointment.objects.create(
            patient=self.patient_a, provider=self.provider, start_time=self.start, end_time=self.end
        )

    def test_owner_can_view_appointment(self):
        self.auth(self.user_a)
        response = self.client.get(f"/api/appointments/{self.appointment.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_non_owner_cannot_view_appointment(self):
        self.auth(self.user_b)
        response = self.client.get(f"/api/appointments/{self.appointment.id}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_non_owner_cannot_cancel_appointment(self):
        self.auth(self.user_b)
        response = self.client.delete(f"/api/appointments/{self.appointment.id}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.appointment.refresh_from_db()
        self.assertEqual(self.appointment.status, "scheduled")

    def test_owner_can_cancel_appointment(self):
        self.auth(self.user_a)
        response = self.client.delete(f"/api/appointments/{self.appointment.id}/")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.appointment.refresh_from_db()
        self.assertEqual(self.appointment.status, "cancelled")

    def test_non_owner_cannot_reschedule_appointment(self):
        self.auth(self.user_b)
        new_start = self.start + timedelta(hours=1)
        response = self.client.patch(
            f"/api/appointments/{self.appointment.id}/",
            {"start_time": new_start.isoformat(), "end_time": (new_start + timedelta(minutes=30)).isoformat()},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_owner_can_reschedule_appointment(self):
        self.auth(self.user_a)
        new_start = self.start + timedelta(hours=1)
        response = self.client.patch(
            f"/api/appointments/{self.appointment.id}/",
            {"start_time": new_start.isoformat(), "end_time": (new_start + timedelta(minutes=30)).isoformat()},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_unauthenticated_requests_rejected(self):
        response = self.client.get(f"/api/appointments/{self.appointment.id}/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
