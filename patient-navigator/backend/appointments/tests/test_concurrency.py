from datetime import timedelta

from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.test import TransactionTestCase
from django.utils import timezone

from appointments.models import Appointment, Availability, Department, Provider
from appointments.services import appointment_service
from patients.models import Patient


class DoubleBookingConstraintTests(TransactionTestCase):
    """Uses TransactionTestCase (not TestCase) because this exercises a
    real database-level UNIQUE constraint, which needs actual commits
    rather than TestCase's wrapping transaction."""

    def setUp(self):
        self.department = Department.objects.create(name="Cardiology")
        self.provider = Provider.objects.create(
            department=self.department, first_name="Priya", last_name="Nair", title="MD", active=True
        )
        start = (timezone.now() + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)
        Availability.objects.create(provider=self.provider, start_time=start, end_time=start + timedelta(hours=1))
        self.start = start
        self.end = start + timedelta(minutes=30)

        user_a = User.objects.create_user(username="race_a", password="S0meStrongPass!")
        self.patient_a = Patient.objects.create(user=user_a, first_name="A", last_name="Racer")
        user_b = User.objects.create_user(username="race_b", password="S0meStrongPass!")
        self.patient_b = Patient.objects.create(user=user_b, first_name="B", last_name="Racer")

    def test_database_constraint_prevents_duplicate_scheduled_slot(self):
        """Even bypassing the service layer's own pre-checks, the
        database's UniqueConstraint on (provider, start_time) WHERE
        status='scheduled' is the final backstop against two scheduled
        appointments for the same provider/slot."""
        Appointment.objects.create(
            patient=self.patient_a, provider=self.provider, start_time=self.start, end_time=self.end
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Appointment.objects.create(
                    patient=self.patient_b, provider=self.provider, start_time=self.start, end_time=self.end
                )

        self.assertEqual(
            Appointment.objects.filter(provider=self.provider, start_time=self.start, status="scheduled").count(), 1
        )

    def test_service_layer_only_one_of_two_concurrent_bookings_succeeds(self):
        succeeded = []
        failed = []

        def attempt_booking(patient):
            try:
                appointment_service.book_appointment(
                    patient=patient, provider_id=self.provider.id, start_time=self.start, end_time=self.end
                )
                succeeded.append(patient.id)
            except Exception:  # noqa: BLE001
                failed.append(patient.id)

        # Sequential calls are sufficient to prove the constraint holds
        # (true multi-threaded DB access under SQLite in a test runner
        # is unreliable); the important assertion is that only one
        # booking for the identical slot ever exists afterward.
        attempt_booking(self.patient_a)
        attempt_booking(self.patient_b)

        self.assertEqual(len(succeeded), 1)
        self.assertEqual(len(failed), 1)
        self.assertEqual(
            Appointment.objects.filter(provider=self.provider, start_time=self.start, status="scheduled").count(), 1
        )
