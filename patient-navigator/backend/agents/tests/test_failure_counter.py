"""
Regression tests: the consecutive-failure counter is updated in the
database, so concurrent turns holding stale Conversation objects can't
overwrite each other's increments.
"""

from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from agents.navigator import service as navigator_service
from conversations.models import Conversation
from escalations.models import Escalation
from patients.models import Patient


class FailureCounterTests(TestCase):
    def setUp(self):
        user = User.objects.create_user(username="counter", password="S0meStrongPass!")
        self.patient = Patient.objects.create(user=user, first_name="Cou", last_name="Nter")
        self.conversation = Conversation.objects.create(patient=self.patient)

    def _fail_turn(self, conversation):
        return navigator_service._apply_failure_tracking(
            conversation=conversation,
            succeeded=False,
            route_result=navigator_service.RouteResult(response_text="fallback"),
        )

    def _db_count(self):
        return Conversation.objects.get(pk=self.conversation.pk).consecutive_agent_failures

    @override_settings(MAX_AGENT_FAILURES_BEFORE_ESCALATION=10)
    def test_increment_builds_on_database_value_not_stale_instance(self):
        stale = Conversation.objects.get(pk=self.conversation.pk)  # sees 0
        Conversation.objects.filter(pk=self.conversation.pk).update(consecutive_agent_failures=2)  # other turns

        self._fail_turn(stale)

        self.assertEqual(self._db_count(), 3)

    @override_settings(MAX_AGENT_FAILURES_BEFORE_ESCALATION=3)
    def test_threshold_reached_through_concurrent_failures_escalates(self):
        stale = Conversation.objects.get(pk=self.conversation.pk)
        Conversation.objects.filter(pk=self.conversation.pk).update(consecutive_agent_failures=2)

        _, escalation_id, _ = self._fail_turn(stale)

        self.assertIsNotNone(escalation_id)
        self.assertEqual(Escalation.objects.get(pk=escalation_id).reason, Escalation.Reason.REPEATED_FAILURE)
        self.assertEqual(self._db_count(), 0)

    def test_success_resets_counter_even_when_instance_is_stale(self):
        stale = Conversation.objects.get(pk=self.conversation.pk)
        Conversation.objects.filter(pk=self.conversation.pk).update(consecutive_agent_failures=2)

        navigator_service._apply_failure_tracking(
            conversation=stale, succeeded=True, route_result=navigator_service.RouteResult(response_text="ok")
        )

        self.assertEqual(self._db_count(), 0)
