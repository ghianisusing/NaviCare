from django.contrib.auth.models import User
from django.test import TestCase

from agents.core.context import MAX_CONTEXT_MESSAGES, build_context
from conversations.models import Conversation, Message
from patients.models import Patient


class BuildContextTests(TestCase):
    def setUp(self):
        user = User.objects.create_user(username="dana", password="S0meStrongPass!")
        self.patient = Patient.objects.create(user=user, first_name="Dana", last_name="Lee")
        self.conversation = Conversation.objects.create(patient=self.patient, summary="Prior summary text.")

    def test_includes_summary(self):
        context = build_context(conversation=self.conversation)
        self.assertEqual(context.summary, "Prior summary text.")

    def test_orders_history_chronologically(self):
        Message.objects.create(conversation=self.conversation, role="user", content="first")
        Message.objects.create(conversation=self.conversation, role="assistant", content="second")
        Message.objects.create(conversation=self.conversation, role="user", content="third")

        context = build_context(conversation=self.conversation)
        contents = [m.content for m in context.history]
        self.assertEqual(contents, ["first", "second", "third"])

    def test_excludes_system_role_messages(self):
        Message.objects.create(conversation=self.conversation, role="user", content="hello")
        Message.objects.create(conversation=self.conversation, role="system", content="internal note")

        context = build_context(conversation=self.conversation)
        roles = [m.role for m in context.history]
        self.assertNotIn("system", roles)

    def test_bounded_to_max_messages(self):
        for i in range(MAX_CONTEXT_MESSAGES + 10):
            Message.objects.create(conversation=self.conversation, role="user", content=f"message {i}")

        context = build_context(conversation=self.conversation)
        self.assertEqual(len(context.history), MAX_CONTEXT_MESSAGES)
        # Should keep the *most recent* messages, not the oldest.
        self.assertEqual(context.history[-1].content, f"message {MAX_CONTEXT_MESSAGES + 9}")
