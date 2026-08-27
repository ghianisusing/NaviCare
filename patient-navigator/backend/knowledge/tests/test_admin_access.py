from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from knowledge.models import HealthcareDocument
from patients.models import Patient


class KnowledgeAdminAccessTests(APITestCase):
    def setUp(self):
        self.patient_user = User.objects.create_user(username="patient", password="S0meStrongPass!")
        Patient.objects.create(user=self.patient_user, first_name="Pat", last_name="Ient")

        self.admin_user = User.objects.create_user(
            username="admin", password="S0meStrongPass!", is_staff=True
        )

        self.document = HealthcareDocument.objects.create(
            title="Test Doc",
            content="Some content.",
            source="Test Source",
            category=HealthcareDocument.Category.GENERAL_HEALTH,
        )

    def auth(self, user):
        token = RefreshToken.for_user(user).access_token
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def test_patient_cannot_list_documents(self):
        self.auth(self.patient_user)
        response = self.client.get("/api/knowledge/documents/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_patient_cannot_create_document(self):
        self.auth(self.patient_user)
        response = self.client.post(
            "/api/knowledge/documents/",
            {
                "title": "Malicious Doc",
                "content": "content",
                "source": "source",
                "category": HealthcareDocument.Category.GENERAL_HEALTH,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_patient_cannot_trigger_ingestion(self):
        self.auth(self.patient_user)
        response = self.client.post("/api/knowledge/ingest/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_unauthenticated_cannot_access_documents(self):
        response = self.client.get("/api/knowledge/documents/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_admin_can_list_documents(self):
        self.auth(self.admin_user)
        response = self.client.get("/api/knowledge/documents/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_admin_can_create_document(self):
        self.auth(self.admin_user)
        response = self.client.post(
            "/api/knowledge/documents/",
            {
                "title": "New Doc",
                "content": "New content about health.",
                "source": "New Source",
                "category": HealthcareDocument.Category.GENERAL_HEALTH,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(HealthcareDocument.objects.filter(title="New Doc").exists())
