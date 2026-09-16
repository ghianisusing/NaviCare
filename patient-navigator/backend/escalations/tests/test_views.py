from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from conversations.models import Conversation
from escalations.models import Escalation
from escalations.services import escalation_service
from patients.models import Patient


class EscalationApiTestCase(APITestCase):
    def setUp(self):
        self.patient_user = User.objects.create_user(username="esc_api_patient", password="S0meStrongPass!")
        self.patient = Patient.objects.create(user=self.patient_user, first_name="A", last_name="Patient")
        self.conversation = Conversation.objects.create(patient=self.patient)

        self.staff_user = User.objects.create_user(username="esc_api_staff", password="S0meStrongPass!", is_staff=True)
        self.other_staff = User.objects.create_user(username="esc_api_staff2", password="S0meStrongPass!", is_staff=True)

        self.escalation = escalation_service.create_escalation(
            patient=self.patient, conversation=self.conversation, reason=Escalation.Reason.PATIENT_REQUEST
        )

    def auth(self, user):
        token = RefreshToken.for_user(user).access_token
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")


class EscalationRbacTests(EscalationApiTestCase):
    def test_patient_cannot_list_escalations(self):
        self.auth(self.patient_user)
        response = self.client.get("/api/escalations/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_patient_cannot_view_escalation_detail(self):
        self.auth(self.patient_user)
        response = self.client.get(f"/api/escalations/{self.escalation.id}/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_patient_cannot_assign_escalation(self):
        self.auth(self.patient_user)
        response = self.client.post(f"/api/escalations/{self.escalation.id}/assign/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_patient_cannot_respond_to_escalation(self):
        self.auth(self.patient_user)
        response = self.client.post(f"/api/escalations/{self.escalation.id}/respond/", {"content": "hi"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_patient_cannot_resolve_escalation(self):
        self.auth(self.patient_user)
        response = self.client.post(f"/api/escalations/{self.escalation.id}/resolve/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_unauthenticated_cannot_list_escalations(self):
        response = self.client.get("/api/escalations/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_staff_can_list_escalations(self):
        self.auth(self.staff_user)
        response = self.client.get("/api/escalations/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_staff_can_view_detail_with_summary(self):
        self.auth(self.staff_user)
        response = self.client.get(f"/api/escalations/{self.escalation.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("summary", response.data)
        self.assertIn("events", response.data)


class EscalationWorkflowApiTests(EscalationApiTestCase):
    def test_staff_can_claim_respond_and_resolve(self):
        self.auth(self.staff_user)

        claim = self.client.post(f"/api/escalations/{self.escalation.id}/assign/")
        self.assertEqual(claim.status_code, status.HTTP_200_OK)

        respond = self.client.post(
            f"/api/escalations/{self.escalation.id}/respond/", {"content": "I can help with this."}, format="json"
        )
        self.assertEqual(respond.status_code, status.HTTP_201_CREATED)
        self.assertEqual(respond.data["role"], "staff")

        resolve = self.client.post(f"/api/escalations/{self.escalation.id}/resolve/")
        self.assertEqual(resolve.status_code, status.HTTP_200_OK)
        self.assertEqual(resolve.data["status"], "resolved")

    def test_two_staff_cannot_both_claim_same_escalation(self):
        self.auth(self.staff_user)
        self.client.post(f"/api/escalations/{self.escalation.id}/assign/")

        self.auth(self.other_staff)
        response = self.client.post(f"/api/escalations/{self.escalation.id}/assign/")
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)

    def test_staff_message_appears_in_patient_conversation(self):
        self.auth(self.staff_user)
        self.client.post(f"/api/escalations/{self.escalation.id}/assign/")
        self.client.post(f"/api/escalations/{self.escalation.id}/respond/", {"content": "Hello!"}, format="json")

        self.auth(self.patient_user)
        response = self.client.get(f"/api/conversations/{self.conversation.id}/")
        roles = [m["role"] for m in response.data["messages"]]
        self.assertIn("staff", roles)

    def test_status_filter_works(self):
        self.auth(self.staff_user)
        response = self.client.get("/api/escalations/?status=resolved")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 0)
