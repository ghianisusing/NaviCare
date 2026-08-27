from unittest import mock

from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from agents.core.llm import LLMResult
from conversations.models import Conversation, Message
from patients.models import Patient


class FakeProvider:
    """Minimal LLM stand-in so conversation-level tests don't depend on
    network access or a real API key."""

    def complete(self, **kwargs):
        return LLMResult(
            text=(
                '{"intent": "GENERAL_NAVIGATION", "urgency": "normal", '
                '"needs_clarification": false, "clarifying_question": null, '
                '"recommended_action": "RESPOND", "target_agent": null, '
                '"response": "I can help you understand your next steps."}'
            ),
            raw={},
        )


class ConversationTests(APITestCase):
    def setUp(self):
        self.user_a = User.objects.create_user(username="patient_a", password="S0meStrongPass!")
        self.patient_a = Patient.objects.create(user=self.user_a, first_name="A", last_name="Patient")

        self.user_b = User.objects.create_user(username="patient_b", password="S0meStrongPass!")
        self.patient_b = Patient.objects.create(user=self.user_b, first_name="B", last_name="Patient")

    def auth(self, user):
        token = RefreshToken.for_user(user).access_token
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def test_create_and_list_conversation(self):
        self.auth(self.user_a)
        create = self.client.post("/api/conversations/", {"title": "New conversation"}, format="json")
        self.assertEqual(create.status_code, status.HTTP_201_CREATED)

        listing = self.client.get("/api/conversations/")
        self.assertEqual(listing.status_code, status.HTTP_200_OK)
        self.assertEqual(len(listing.data), 1)

    @mock.patch("agents.navigator.agent.get_llm_provider", return_value=FakeProvider())
    def test_send_message_persists_and_gets_navigator_reply(self, _mock_provider):
        self.auth(self.user_a)
        conversation = Conversation.objects.create(patient=self.patient_a)

        response = self.client.post(
            f"/api/conversations/{conversation.id}/messages/",
            {"content": "I need help finding a doctor."},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["role"], "assistant")
        self.assertTrue(len(response.data["content"]) > 0)

        messages = Message.objects.filter(conversation=conversation)
        self.assertEqual(messages.count(), 2)
        self.assertEqual(messages.first().role, "user")

    def test_send_message_falls_back_safely_when_llm_unconfigured(self):
        # No LLM_API_KEY is set in the test environment — this exercises
        # the real fallback path end-to-end rather than mocking it away.
        self.auth(self.user_a)
        conversation = Conversation.objects.create(patient=self.patient_a)

        response = self.client.post(
            f"/api/conversations/{conversation.id}/messages/",
            {"content": "I need help finding a doctor."},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["role"], "assistant")
        self.assertTrue(len(response.data["content"]) > 0)

    def test_empty_message_rejected(self):
        self.auth(self.user_a)
        conversation = Conversation.objects.create(patient=self.patient_a)
        response = self.client.post(
            f"/api/conversations/{conversation.id}/messages/", {"content": "   "}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_patient_cannot_access_another_patients_conversation(self):
        conversation = Conversation.objects.create(patient=self.patient_a)

        self.auth(self.user_b)
        detail = self.client.get(f"/api/conversations/{conversation.id}/")
        self.assertEqual(detail.status_code, status.HTTP_404_NOT_FOUND)

        send = self.client.post(
            f"/api/conversations/{conversation.id}/messages/", {"content": "hi"}, format="json"
        )
        self.assertEqual(send.status_code, status.HTTP_404_NOT_FOUND)

    def test_unauthenticated_requests_rejected(self):
        response = self.client.get("/api/conversations/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
