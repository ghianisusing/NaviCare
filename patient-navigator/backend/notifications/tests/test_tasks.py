from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from follow_ups.models import FollowUp, Reminder
from follow_ups.services import follow_up_service
from notifications.models import Notification
from notifications.tasks import process_due_reminders, run_maintenance_cycle
from patients.models import Patient


class ProcessDueRemindersTests(TestCase):
    def setUp(self):
        user = User.objects.create_user(username="worker_patient", password="S0meStrongPass!")
        self.patient = Patient.objects.create(user=user, first_name="Worker", last_name="Patient")
        self.follow_up = follow_up_service.create_follow_up(patient=self.patient, title="Contact clinic")
        self.reminder = follow_up_service.create_reminder(
            patient=self.patient, follow_up_id=self.follow_up.id, scheduled_for=timezone.now() + timedelta(seconds=1)
        )

    def _as_of(self):
        return timezone.now() + timedelta(seconds=5)

    def test_due_reminder_produces_a_notification(self):
        sent = process_due_reminders(as_of=self._as_of())
        self.assertEqual(sent, 1)
        self.assertEqual(Notification.objects.filter(patient=self.patient).count(), 1)

        self.reminder.refresh_from_db()
        self.assertEqual(self.reminder.status, Reminder.Status.SENT)
        self.assertIsNotNone(self.reminder.sent_at)

    def test_running_twice_does_not_duplicate_notification(self):
        as_of = self._as_of()
        first = process_due_reminders(as_of=as_of)
        second = process_due_reminders(as_of=as_of)

        self.assertEqual(first, 1)
        self.assertEqual(second, 0)
        self.assertEqual(Notification.objects.filter(patient=self.patient).count(), 1)

    def test_not_yet_due_reminder_is_not_sent(self):
        Reminder.objects.filter(pk=self.reminder.pk).update(
            scheduled_for=timezone.now() + timedelta(days=5)
        )
        sent = process_due_reminders(as_of=timezone.now())
        self.assertEqual(sent, 0)
        self.assertEqual(Notification.objects.count(), 0)

    def test_cancelled_follow_up_reminder_is_not_sent(self):
        follow_up_service.cancel_follow_up(patient=self.patient, follow_up_id=self.follow_up.id)
        sent = process_due_reminders(as_of=self._as_of())
        self.assertEqual(sent, 0)
        self.assertEqual(Notification.objects.count(), 0)

    def test_completed_follow_up_reminder_is_not_sent(self):
        follow_up_service.complete_follow_up(patient=self.patient, follow_up_id=self.follow_up.id)
        sent = process_due_reminders(as_of=self._as_of())
        self.assertEqual(sent, 0)

    def test_cancelled_reminder_directly_is_not_sent(self):
        follow_up_service.cancel_reminder(patient=self.patient, reminder_id=self.reminder.id)
        sent = process_due_reminders(as_of=self._as_of())
        self.assertEqual(sent, 0)

    def test_notification_references_follow_up(self):
        process_due_reminders(as_of=self._as_of())
        notification = Notification.objects.get(patient=self.patient)
        self.assertEqual(notification.related_follow_up_id, self.follow_up.id)
        self.assertEqual(notification.type, Notification.Type.FOLLOW_UP_REMINDER)

    def test_appointment_reminder_uses_appointment_notification_type(self):
        from appointments.models import Appointment, Department, Provider

        department = Department.objects.create(name="Cardiology")
        provider = Provider.objects.create(department=department, first_name="Priya", last_name="Nair", active=True)
        appointment = Appointment.objects.create(
            patient=self.patient,
            provider=provider,
            start_time=timezone.now() + timedelta(days=1),
            end_time=timezone.now() + timedelta(days=1, minutes=30),
        )
        follow_up = follow_up_service.create_follow_up(
            patient=self.patient, title="Upcoming appointment", appointment=appointment, due_at=appointment.start_time
        )
        follow_up_service.create_reminder(
            patient=self.patient, follow_up_id=follow_up.id, scheduled_for=timezone.now() + timedelta(seconds=1)
        )

        process_due_reminders(as_of=self._as_of())

        notification = Notification.objects.get(related_follow_up=follow_up)
        self.assertEqual(notification.type, Notification.Type.APPOINTMENT_REMINDER)
        self.assertEqual(notification.related_appointment_id, appointment.id)


class RunMaintenanceCycleTests(TestCase):
    def setUp(self):
        user = User.objects.create_user(username="maintenance_patient", password="S0meStrongPass!")
        self.patient = Patient.objects.create(user=user, first_name="Maint", last_name="Patient")

    def test_maintenance_cycle_sends_reminders_and_expires_follow_ups(self):
        active_follow_up = follow_up_service.create_follow_up(patient=self.patient, title="Active")
        follow_up_service.create_reminder(
            patient=self.patient, follow_up_id=active_follow_up.id, scheduled_for=timezone.now() + timedelta(seconds=1)
        )
        FollowUp.objects.create(patient=self.patient, title="Overdue", due_at=timezone.now() - timedelta(days=1))

        import time

        time.sleep(1.1)
        result = run_maintenance_cycle()

        self.assertEqual(result["reminders_sent"], 1)
        self.assertEqual(result["follow_ups_expired"], 1)
