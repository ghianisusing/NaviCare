from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from notifications.models import Notification
from patients.models import Patient


class NotificationApiTests(APITestCase):
    def setUp(self):
        self.user_a = User.objects.create_user(username="notif_a", password="S0meStrongPass!")
        self.patient_a = Patient.objects.create(user=self.user_a, first_name="A", last_name="Patient")
        self.user_b = User.objects.create_user(username="notif_b", password="S0meStrongPass!")
        self.patient_b = Patient.objects.create(user=self.user_b, first_name="B", last_name="Patient")

        self.notification_a = Notification.objects.create(
            patient=self.patient_a, type="system", title="Hello", message="Test message"
        )
        self.notification_b = Notification.objects.create(
            patient=self.patient_b, type="system", title="Hello B", message="Test message B"
        )

    def auth(self, user):
        token = RefreshToken.for_user(user).access_token
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def test_list_only_shows_own_notifications(self):
        self.auth(self.user_a)
        response = self.client.get("/api/notifications/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = [n["id"] for n in response.data]
        self.assertIn(self.notification_a.id, ids)
        self.assertNotIn(self.notification_b.id, ids)

    def test_unread_filter(self):
        Notification.objects.create(patient=self.patient_a, type="system", title="Read one", message="x", read=True)
        self.auth(self.user_a)
        response = self.client.get("/api/notifications/?unread=1")
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["id"], self.notification_a.id)

    def test_owner_can_mark_read(self):
        self.auth(self.user_a)
        response = self.client.patch(f"/api/notifications/{self.notification_a.id}/read/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.notification_a.refresh_from_db()
        self.assertTrue(self.notification_a.read)
        self.assertIsNotNone(self.notification_a.read_at)

    def test_non_owner_cannot_mark_read(self):
        self.auth(self.user_b)
        response = self.client.patch(f"/api/notifications/{self.notification_a.id}/read/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.notification_a.refresh_from_db()
        self.assertFalse(self.notification_a.read)

    def test_unauthenticated_rejected(self):
        response = self.client.get("/api/notifications/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
