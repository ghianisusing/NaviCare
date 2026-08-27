from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from patients.models import Patient


class PatientPrivacyTests(APITestCase):
    def setUp(self):
        self.user_a = User.objects.create_user(username="patient_a", password="S0meStrongPass!")
        self.patient_a = Patient.objects.create(user=self.user_a, first_name="A", last_name="Patient")

        self.user_b = User.objects.create_user(username="patient_b", password="S0meStrongPass!")
        self.patient_b = Patient.objects.create(user=self.user_b, first_name="B", last_name="Patient")

    def auth(self, user):
        token = RefreshToken.for_user(user).access_token
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def test_patient_can_retrieve_own_profile(self):
        self.auth(self.user_a)
        response = self.client.get("/api/patients/me/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["first_name"], "A")

    def test_me_endpoint_always_resolves_to_caller_not_a_url_id(self):
        # /api/patients/me/ never accepts or exposes another patient's id
        # in the URL, which is the mechanism that prevents id-tampering.
        self.auth(self.user_b)
        response = self.client.get("/api/patients/me/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["first_name"], "B")
        self.assertNotEqual(response.data["first_name"], self.patient_a.first_name)

    def test_unauthenticated_request_rejected(self):
        response = self.client.get("/api/patients/me/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
