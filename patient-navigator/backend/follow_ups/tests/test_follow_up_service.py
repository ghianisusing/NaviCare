from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from follow_ups.models import FollowUp, Reminder
from follow_ups.services import follow_up_service
from follow_ups.services.exceptions import InvalidFollowUpRequestError, NotOwnerError
from patients.models import Patient


class FollowUpServiceTestCase(TestCase):
    def setUp(self):
        user_a = User.objects.create_user(username="fu_patient_a", password="S0meStrongPass!")
        self.patient_a = Patient.objects.create(user=user_a, first_name="A", last_name="Patient")
        user_b = User.objects.create_user(username="fu_patient_b", password="S0meStrongPass!")
        self.patient_b = Patient.objects.create(user=user_b, first_name="B", last_name="Patient")


class CreateFollowUpTests(FollowUpServiceTestCase):
    def test_creates_follow_up_without_due_date(self):
        follow_up = follow_up_service.create_follow_up(patient=self.patient_a, title="Contact clinic")
        self.assertEqual(follow_up.status, FollowUp.Status.PENDING)
        self.assertIsNone(follow_up.due_at)

    def test_creates_follow_up_with_due_date(self):
        due = timezone.now() + timedelta(days=3)
        follow_up = follow_up_service.create_follow_up(patient=self.patient_a, title="Review labs", due_at=due)
        self.assertEqual(follow_up.due_at, due)

    def test_empty_title_rejected(self):
        with self.assertRaises(InvalidFollowUpRequestError):
            follow_up_service.create_follow_up(patient=self.patient_a, title="   ")

    def test_past_due_date_rejected(self):
        with self.assertRaises(InvalidFollowUpRequestError):
            follow_up_service.create_follow_up(
                patient=self.patient_a, title="Task", due_at=timezone.now() - timedelta(days=1)
            )

    def test_invalid_priority_rejected(self):
        with self.assertRaises(InvalidFollowUpRequestError):
            follow_up_service.create_follow_up(patient=self.patient_a, title="Task", priority="urgent-ish")


class GetPatientFollowUpsTests(FollowUpServiceTestCase):
    def test_only_returns_own_follow_ups(self):
        follow_up_service.create_follow_up(patient=self.patient_a, title="A's task")
        follow_up_service.create_follow_up(patient=self.patient_b, title="B's task")

        follow_ups_a = follow_up_service.get_patient_follow_ups(patient=self.patient_a)
        self.assertEqual(len(follow_ups_a), 1)
        self.assertEqual(follow_ups_a[0].title, "A's task")

    def test_filters_by_status(self):
        follow_up = follow_up_service.create_follow_up(patient=self.patient_a, title="Task")
        follow_up_service.complete_follow_up(patient=self.patient_a, follow_up_id=follow_up.id)

        pending = follow_up_service.get_patient_follow_ups(patient=self.patient_a, status="pending")
        completed = follow_up_service.get_patient_follow_ups(patient=self.patient_a, status="completed")
        self.assertEqual(len(pending), 0)
        self.assertEqual(len(completed), 1)


class CompleteFollowUpTests(FollowUpServiceTestCase):
    def setUp(self):
        super().setUp()
        self.follow_up = follow_up_service.create_follow_up(patient=self.patient_a, title="Contact clinic")

    def test_owner_can_complete(self):
        completed = follow_up_service.complete_follow_up(patient=self.patient_a, follow_up_id=self.follow_up.id)
        self.assertEqual(completed.status, FollowUp.Status.COMPLETED)
        self.assertIsNotNone(completed.completed_at)

    def test_non_owner_cannot_complete(self):
        with self.assertRaises(NotOwnerError):
            follow_up_service.complete_follow_up(patient=self.patient_b, follow_up_id=self.follow_up.id)

    def test_completing_cancels_pending_reminders(self):
        reminder = follow_up_service.create_reminder(
            patient=self.patient_a, follow_up_id=self.follow_up.id, scheduled_for=timezone.now() + timedelta(hours=1)
        )
        follow_up_service.complete_follow_up(patient=self.patient_a, follow_up_id=self.follow_up.id)
        reminder.refresh_from_db()
        self.assertEqual(reminder.status, Reminder.Status.CANCELLED)

    def test_cannot_complete_twice(self):
        follow_up_service.complete_follow_up(patient=self.patient_a, follow_up_id=self.follow_up.id)
        with self.assertRaises(InvalidFollowUpRequestError):
            follow_up_service.complete_follow_up(patient=self.patient_a, follow_up_id=self.follow_up.id)


class CancelFollowUpTests(FollowUpServiceTestCase):
    def setUp(self):
        super().setUp()
        self.follow_up = follow_up_service.create_follow_up(patient=self.patient_a, title="Contact clinic")

    def test_owner_can_cancel(self):
        cancelled = follow_up_service.cancel_follow_up(patient=self.patient_a, follow_up_id=self.follow_up.id)
        self.assertEqual(cancelled.status, FollowUp.Status.CANCELLED)

    def test_non_owner_cannot_cancel(self):
        with self.assertRaises(NotOwnerError):
            follow_up_service.cancel_follow_up(patient=self.patient_b, follow_up_id=self.follow_up.id)

    def test_cancelling_cancels_pending_reminders(self):
        reminder = follow_up_service.create_reminder(
            patient=self.patient_a, follow_up_id=self.follow_up.id, scheduled_for=timezone.now() + timedelta(hours=1)
        )
        follow_up_service.cancel_follow_up(patient=self.patient_a, follow_up_id=self.follow_up.id)
        reminder.refresh_from_db()
        self.assertEqual(reminder.status, Reminder.Status.CANCELLED)


class ExpiredFollowUpTests(FollowUpServiceTestCase):
    def test_past_due_pending_follow_up_marked_expired(self):
        follow_up = FollowUp.objects.create(
            patient=self.patient_a, title="Overdue task", due_at=timezone.now() - timedelta(days=2)
        )
        count = follow_up_service.mark_expired_follow_ups()
        follow_up.refresh_from_db()
        self.assertEqual(count, 1)
        self.assertEqual(follow_up.status, FollowUp.Status.EXPIRED)

    def test_future_due_follow_up_not_expired(self):
        follow_up = follow_up_service.create_follow_up(
            patient=self.patient_a, title="Future task", due_at=timezone.now() + timedelta(days=2)
        )
        follow_up_service.mark_expired_follow_ups()
        follow_up.refresh_from_db()
        self.assertEqual(follow_up.status, FollowUp.Status.PENDING)

    def test_completed_follow_up_not_marked_expired(self):
        follow_up = FollowUp.objects.create(
            patient=self.patient_a,
            title="Done task",
            due_at=timezone.now() - timedelta(days=2),
            status=FollowUp.Status.COMPLETED,
        )
        follow_up_service.mark_expired_follow_ups()
        follow_up.refresh_from_db()
        self.assertEqual(follow_up.status, FollowUp.Status.COMPLETED)


class ReminderServiceTests(FollowUpServiceTestCase):
    def setUp(self):
        super().setUp()
        self.follow_up = follow_up_service.create_follow_up(patient=self.patient_a, title="Contact clinic")

    def test_create_reminder(self):
        reminder = follow_up_service.create_reminder(
            patient=self.patient_a, follow_up_id=self.follow_up.id, scheduled_for=timezone.now() + timedelta(hours=2)
        )
        self.assertEqual(reminder.status, Reminder.Status.SCHEDULED)

    def test_reminder_in_the_past_rejected(self):
        with self.assertRaises(InvalidFollowUpRequestError):
            follow_up_service.create_reminder(
                patient=self.patient_a, follow_up_id=self.follow_up.id, scheduled_for=timezone.now() - timedelta(hours=1)
            )

    def test_naive_datetime_rejected(self):
        import datetime

        with self.assertRaises(InvalidFollowUpRequestError):
            follow_up_service.create_reminder(
                patient=self.patient_a,
                follow_up_id=self.follow_up.id,
                scheduled_for=datetime.datetime.now() + timedelta(hours=1),
            )

    def test_non_owner_cannot_create_reminder(self):
        with self.assertRaises(NotOwnerError):
            follow_up_service.create_reminder(
                patient=self.patient_b, follow_up_id=self.follow_up.id, scheduled_for=timezone.now() + timedelta(hours=1)
            )

    def test_cancel_reminder(self):
        reminder = follow_up_service.create_reminder(
            patient=self.patient_a, follow_up_id=self.follow_up.id, scheduled_for=timezone.now() + timedelta(hours=1)
        )
        cancelled = follow_up_service.cancel_reminder(patient=self.patient_a, reminder_id=reminder.id)
        self.assertEqual(cancelled.status, Reminder.Status.CANCELLED)

    def test_non_owner_cannot_cancel_reminder(self):
        reminder = follow_up_service.create_reminder(
            patient=self.patient_a, follow_up_id=self.follow_up.id, scheduled_for=timezone.now() + timedelta(hours=1)
        )
        with self.assertRaises(NotOwnerError):
            follow_up_service.cancel_reminder(patient=self.patient_b, reminder_id=reminder.id)

    def test_get_due_reminders(self):
        due_soon = follow_up_service.create_reminder(
            patient=self.patient_a, follow_up_id=self.follow_up.id, scheduled_for=timezone.now() + timedelta(seconds=1)
        )
        follow_up_service.create_reminder(
            patient=self.patient_a, follow_up_id=self.follow_up.id, scheduled_for=timezone.now() + timedelta(days=5)
        )

        due = follow_up_service.get_due_reminders(as_of=timezone.now() + timedelta(seconds=2))
        due_ids = [r.id for r in due]
        self.assertIn(due_soon.id, due_ids)
        self.assertEqual(len(due_ids), 1)
