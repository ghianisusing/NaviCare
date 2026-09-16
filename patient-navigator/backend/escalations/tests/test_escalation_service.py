from django.contrib.auth.models import User
from django.test import TestCase

from conversations.models import Conversation
from escalations.models import Escalation, EscalationEvent
from escalations.services import escalation_service
from escalations.services.exceptions import AlreadyAssignedError, InvalidEscalationRequestError
from patients.models import Patient


class EscalationServiceTestCase(TestCase):
    def setUp(self):
        user = User.objects.create_user(username="esc_patient", password="S0meStrongPass!")
        self.patient = Patient.objects.create(user=user, first_name="Esc", last_name="Patient")
        self.conversation = Conversation.objects.create(patient=self.patient)

        self.staff_a = User.objects.create_user(username="staff_a", password="S0meStrongPass!", is_staff=True)
        self.staff_b = User.objects.create_user(username="staff_b", password="S0meStrongPass!", is_staff=True)


class CreateEscalationTests(EscalationServiceTestCase):
    def test_creates_escalation_with_valid_reason(self):
        escalation = escalation_service.create_escalation(
            patient=self.patient, conversation=self.conversation, reason=Escalation.Reason.PATIENT_REQUEST
        )
        self.assertEqual(escalation.status, Escalation.Status.PENDING)
        self.assertTrue(EscalationEvent.objects.filter(escalation=escalation, action="created").exists())

    def test_invalid_reason_rejected(self):
        with self.assertRaises(InvalidEscalationRequestError):
            escalation_service.create_escalation(
                patient=self.patient, conversation=self.conversation, reason="made_up_reason"
            )

    def test_invalid_priority_rejected(self):
        with self.assertRaises(InvalidEscalationRequestError):
            escalation_service.create_escalation(
                patient=self.patient,
                conversation=self.conversation,
                reason=Escalation.Reason.PATIENT_REQUEST,
                priority="critical",
            )

    def test_duplicate_open_escalation_is_idempotent(self):
        first = escalation_service.create_escalation(
            patient=self.patient, conversation=self.conversation, reason=Escalation.Reason.PATIENT_REQUEST
        )
        second = escalation_service.create_escalation(
            patient=self.patient, conversation=self.conversation, reason=Escalation.Reason.OUT_OF_SCOPE
        )
        self.assertEqual(first.id, second.id)
        self.assertEqual(Escalation.objects.filter(conversation=self.conversation).count(), 1)

    def test_summary_includes_conversation_summary(self):
        self.conversation.summary = "Patient wants help rescheduling."
        self.conversation.save()
        escalation = escalation_service.create_escalation(
            patient=self.patient, conversation=self.conversation, reason=Escalation.Reason.ADMINISTRATIVE_ISSUE
        )
        self.assertEqual(escalation.summary["summary"], "Patient wants help rescheduling.")

    def test_summary_has_expected_structure(self):
        escalation = escalation_service.create_escalation(
            patient=self.patient, conversation=self.conversation, reason=Escalation.Reason.PATIENT_REQUEST
        )
        for key in ("summary", "relevant_appointments", "relevant_follow_ups", "agent_actions"):
            self.assertIn(key, escalation.summary)


class AssignEscalationTests(EscalationServiceTestCase):
    def setUp(self):
        super().setUp()
        self.escalation = escalation_service.create_escalation(
            patient=self.patient, conversation=self.conversation, reason=Escalation.Reason.PATIENT_REQUEST
        )

    def test_staff_can_claim_pending_escalation(self):
        assigned = escalation_service.assign_escalation(staff_user=self.staff_a, escalation_id=self.escalation.id)
        self.assertEqual(assigned.status, Escalation.Status.ASSIGNED)
        self.assertEqual(assigned.assigned_to, self.staff_a)

    def test_second_staff_cannot_claim_already_assigned_escalation(self):
        escalation_service.assign_escalation(staff_user=self.staff_a, escalation_id=self.escalation.id)
        with self.assertRaises(AlreadyAssignedError):
            escalation_service.assign_escalation(staff_user=self.staff_b, escalation_id=self.escalation.id)

    def test_same_staff_can_reassign_to_self_idempotently(self):
        escalation_service.assign_escalation(staff_user=self.staff_a, escalation_id=self.escalation.id)
        reassigned = escalation_service.assign_escalation(staff_user=self.staff_a, escalation_id=self.escalation.id)
        self.assertEqual(reassigned.assigned_to, self.staff_a)


class StaffResponseTests(EscalationServiceTestCase):
    def setUp(self):
        super().setUp()
        self.escalation = escalation_service.create_escalation(
            patient=self.patient, conversation=self.conversation, reason=Escalation.Reason.PATIENT_REQUEST
        )
        escalation_service.assign_escalation(staff_user=self.staff_a, escalation_id=self.escalation.id)

    def test_assigned_staff_can_respond(self):
        message = escalation_service.send_staff_response(
            staff_user=self.staff_a, escalation_id=self.escalation.id, content="I can help with that."
        )
        self.assertEqual(message.role, "staff")
        self.assertEqual(message.sender_staff, self.staff_a)
        self.escalation.refresh_from_db()
        self.assertEqual(self.escalation.status, Escalation.Status.IN_PROGRESS)

    def test_unassigned_staff_cannot_respond(self):
        with self.assertRaises(InvalidEscalationRequestError):
            escalation_service.send_staff_response(
                staff_user=self.staff_b, escalation_id=self.escalation.id, content="Butting in."
            )

    def test_empty_response_rejected(self):
        with self.assertRaises(InvalidEscalationRequestError):
            escalation_service.send_staff_response(
                staff_user=self.staff_a, escalation_id=self.escalation.id, content="   "
            )

    def test_response_creates_notification_for_patient(self):
        from notifications.models import Notification

        escalation_service.send_staff_response(
            staff_user=self.staff_a, escalation_id=self.escalation.id, content="Following up on your request."
        )
        self.assertTrue(Notification.objects.filter(patient=self.patient).exists())

    def test_notification_does_not_leak_internal_details(self):
        from notifications.models import Notification

        escalation_service.send_staff_response(
            staff_user=self.staff_a, escalation_id=self.escalation.id, content="Secret internal note about routing."
        )
        notification = Notification.objects.get(patient=self.patient)
        self.assertNotIn("Secret internal note", notification.message)


class ResolveEscalationTests(EscalationServiceTestCase):
    def setUp(self):
        super().setUp()
        self.escalation = escalation_service.create_escalation(
            patient=self.patient, conversation=self.conversation, reason=Escalation.Reason.PATIENT_REQUEST
        )
        escalation_service.assign_escalation(staff_user=self.staff_a, escalation_id=self.escalation.id)

    def test_assigned_staff_can_resolve(self):
        resolved = escalation_service.resolve_escalation(staff_user=self.staff_a, escalation_id=self.escalation.id)
        self.assertEqual(resolved.status, Escalation.Status.RESOLVED)
        self.assertIsNotNone(resolved.resolved_at)

    def test_other_staff_cannot_resolve(self):
        with self.assertRaises(InvalidEscalationRequestError):
            escalation_service.resolve_escalation(staff_user=self.staff_b, escalation_id=self.escalation.id)

    def test_cannot_resolve_twice(self):
        escalation_service.resolve_escalation(staff_user=self.staff_a, escalation_id=self.escalation.id)
        with self.assertRaises(InvalidEscalationRequestError):
            escalation_service.resolve_escalation(staff_user=self.staff_a, escalation_id=self.escalation.id)

    def test_audit_trail_records_full_lifecycle(self):
        escalation_service.send_staff_response(
            staff_user=self.staff_a, escalation_id=self.escalation.id, content="On it."
        )
        escalation_service.resolve_escalation(staff_user=self.staff_a, escalation_id=self.escalation.id)

        actions = list(EscalationEvent.objects.filter(escalation=self.escalation).values_list("action", flat=True))
        self.assertEqual(actions, ["created", "assigned", "staff_response_sent", "resolved"])
