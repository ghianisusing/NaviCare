from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.test import APITestCase

from patients.models import Patient


class RegistrationTests(APITestCase):
    def test_registration_creates_user_and_patient(self):
        response = self.client.post(
            "/api/auth/register/",
            {
                "username": "alice",
                "email": "alice@example.com",
                "password": "S0meStrongPass!",
                "first_name": "Alice",
                "last_name": "Nguyen",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("access", response.data)
        self.assertTrue(User.objects.filter(username="alice").exists())
        self.assertTrue(Patient.objects.filter(user__username="alice").exists())

    def test_registration_rejects_duplicate_email(self):
        User.objects.create_user(username="bob", email="bob@example.com", password="whatever123")
        response = self.client.post(
            "/api/auth/register/",
            {
                "username": "bob2",
                "email": "bob@example.com",
                "password": "S0meStrongPass!",
                "first_name": "Bob",
                "last_name": "Two",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class LoginTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="carol", password="S0meStrongPass!")
        Patient.objects.create(user=self.user, first_name="Carol", last_name="Diaz")

    def test_login_with_valid_credentials(self):
        response = self.client.post(
            "/api/auth/login/", {"username": "carol", "password": "S0meStrongPass!"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)

    def test_login_with_invalid_credentials_fails(self):
        response = self.client.post(
            "/api/auth/login/", {"username": "carol", "password": "wrong-password"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn("error", response.data)

    def test_me_requires_authentication(self):
        response = self.client.get("/api/auth/me/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
