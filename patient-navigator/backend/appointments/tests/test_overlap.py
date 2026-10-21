"""
Regression tests: bookings and reschedules reject any *overlapping*
time, not only an identical start_time, for both the provider and the
patient.
"""

from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase, TransactionTestCase
from django.utils import timezone

from appointments.models import Appointment, Availability, Department, Provider
from appointments.services import appointment_service
from appointments.services.exceptions import PatientScheduleConflictError, SlotUnavailableError
from core.tests.concurrency import requires_postgres, run_concurrently
from patients.models import Patient


def _make_world(test):
    department = Department.objects.create(name="Neurology")
    test.provider = Provider.objects.create(department=department, first_name="Ada", last_name="Kim", title="MD")
    test.other_provider = Provider.objects.create(department=department, first_name="Ben", last_name="Roy", title="MD")
    test.nine = (timezone.now() + timedelta(days=3)).replace(hour=9, minute=0, second=0, microsecond=0)
    for provider in (test.provider, test.other_provider):
        Availability.objects.create(provider=provider, start_time=test.nine, end_time=test.nine + timedelta(hours=2))

    def patient(name):
        user = User.objects.create_user(username=f"overlap_{name}", password="S0meStrongPass!")
        return Patient.objects.create(user=user, first_name=name, last_name="Overlap")

    test.patient_a = patient("a")
    test.patient_b = patient("b")


def _at(test, minutes):
    return test.nine + timedelta(minutes=minutes)


class BookingOverlapTests(TestCase):
    def setUp(self):
        _make_world(self)
        self.existing = appointment_service.book_appointment(
            patient=self.patient_a, provider_id=self.provider.id, start_time=_at(self, 0), end_time=_at(self, 30)
        )

    def test_partially_overlapping_booking_with_same_provider_rejected(self):
        with self.assertRaises(SlotUnavailableError):
            appointment_service.book_appointment(
                patient=self.patient_b, provider_id=self.provider.id, start_time=_at(self, 15), end_time=_at(self, 45)
            )

    def test_booking_inside_existing_one_rejected(self):
        with self.assertRaises(SlotUnavailableError):
            appointment_service.book_appointment(
                patient=self.patient_b, provider_id=self.provider.id, start_time=_at(self, 10), end_time=_at(self, 20)
            )

    def test_adjacent_booking_allowed(self):
        appointment_service.book_appointment(
            patient=self.patient_b, provider_id=self.provider.id, start_time=_at(self, 30), end_time=_at(self, 60)
        )

    def test_patient_cannot_double_book_across_providers(self):
        with self.assertRaises(PatientScheduleConflictError):
            appointment_service.book_appointment(
                patient=self.patient_a,
                provider_id=self.other_provider.id,
                start_time=_at(self, 15),
                end_time=_at(self, 45),
            )

    def test_cancelled_appointment_does_not_block(self):
        appointment_service.cancel_appointment(patient=self.patient_a, appointment_id=self.existing.id)
        appointment_service.book_appointment(
            patient=self.patient_b, provider_id=self.provider.id, start_time=_at(self, 15), end_time=_at(self, 45)
        )

    def test_slot_search_hides_slots_overlapping_an_off_grid_booking(self):
        appointment_service.book_appointment(
            patient=self.patient_b, provider_id=self.provider.id, start_time=_at(self, 45), end_time=_at(self, 75)
        )
        starts = {
            s.start_time
            for s in appointment_service.find_available_slots(provider_id=self.provider.id, on_date=self.nine.date())
        }
        # 9:00 is booked; 9:30 and 10:00 overlap the 9:45-10:15 booking.
        self.assertEqual(starts, {_at(self, 90)})


class RescheduleOverlapTests(TestCase):
    def setUp(self):
        _make_world(self)
        appointment_service.book_appointment(
            patient=self.patient_a, provider_id=self.provider.id, start_time=_at(self, 0), end_time=_at(self, 30)
        )
        self.moving = appointment_service.book_appointment(
            patient=self.patient_b, provider_id=self.provider.id, start_time=_at(self, 60), end_time=_at(self, 90)
        )

    def test_reschedule_into_partial_overlap_rejected(self):
        with self.assertRaises(SlotUnavailableError):
            appointment_service.reschedule_appointment(
                patient=self.patient_b,
                appointment_id=self.moving.id,
                new_start_time=_at(self, 15),
                new_end_time=_at(self, 45),
            )
        self.moving.refresh_from_db()
        self.assertEqual(self.moving.start_time, _at(self, 60))

    def test_reschedule_overlapping_its_own_old_time_allowed(self):
        appointment_service.reschedule_appointment(
            patient=self.patient_b, appointment_id=self.moving.id, new_start_time=_at(self, 75), new_end_time=_at(self, 105)
        )

    def test_reschedule_into_patients_other_appointment_rejected(self):
        other = appointment_service.book_appointment(
            patient=self.patient_b, provider_id=self.other_provider.id, start_time=_at(self, 30), end_time=_at(self, 60)
        )
        with self.assertRaises(PatientScheduleConflictError):
            appointment_service.reschedule_appointment(
                patient=self.patient_b,
                appointment_id=self.moving.id,
                new_start_time=_at(self, 45),
                new_end_time=_at(self, 75),
            )
        self.assertTrue(Appointment.objects.filter(pk=other.pk, status="scheduled").exists())


@requires_postgres
class OverlapRaceTests(TransactionTestCase):
    def setUp(self):
        _make_world(self)

    def _book(self, patient, provider, start_minutes):
        return lambda: appointment_service.book_appointment(
            patient=patient,
            provider_id=provider.id,
            start_time=_at(self, start_minutes),
            end_time=_at(self, start_minutes + 30),
        )

    def test_concurrent_overlapping_bookings_for_one_provider(self):
        outcomes = run_concurrently(
            self._book(self.patient_a, self.provider, 0), self._book(self.patient_b, self.provider, 15)
        )
        self.assertEqual(sum(isinstance(o, Appointment) for o in outcomes), 1, outcomes)
        self.assertEqual(sum(isinstance(o, SlotUnavailableError) for o in outcomes), 1, outcomes)

    def test_concurrent_bookings_for_one_patient_across_providers(self):
        outcomes = run_concurrently(
            self._book(self.patient_a, self.provider, 0), self._book(self.patient_a, self.other_provider, 0)
        )
        self.assertEqual(sum(isinstance(o, Appointment) for o in outcomes), 1, outcomes)
        self.assertEqual(sum(isinstance(o, PatientScheduleConflictError) for o in outcomes), 1, outcomes)
