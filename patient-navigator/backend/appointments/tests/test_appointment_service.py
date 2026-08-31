from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from appointments.models import Appointment, Availability, Department, Provider
from appointments.services import appointment_service
from appointments.services.exceptions import (
    AppointmentNotFoundError,
    InvalidAppointmentRequestError,
    NotOwnerError,
    SlotUnavailableError,
)
from patients.models import Patient


class AppointmentServiceTestCase(TestCase):
    def setUp(self):
        self.department = Department.objects.create(name="Dermatology")
        self.provider = Provider.objects.create(
            department=self.department, first_name="Alex", last_name="Rivera", title="MD", active=True
        )
        tomorrow_9am = (timezone.now() + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)
        self.availability = Availability.objects.create(
            provider=self.provider, start_time=tomorrow_9am, end_time=tomorrow_9am + timedelta(hours=2)
        )
        self.slot_start = tomorrow_9am
        self.slot_end = tomorrow_9am + timedelta(minutes=30)

        user_a = User.objects.create_user(username="patient_a", password="S0meStrongPass!")
        self.patient_a = Patient.objects.create(user=user_a, first_name="A", last_name="Patient")
        user_b = User.objects.create_user(username="patient_b", password="S0meStrongPass!")
        self.patient_b = Patient.objects.create(user=user_b, first_name="B", last_name="Patient")


class FindAvailableSlotsTests(AppointmentServiceTestCase):
    def test_finds_slots_within_availability_window(self):
        slots = appointment_service.find_available_slots(department_name="Dermatology")
        self.assertGreater(len(slots), 0)
        self.assertEqual(slots[0].start_time, self.slot_start)

    def test_excludes_already_booked_slots(self):
        appointment_service.book_appointment(
            patient=self.patient_a, provider_id=self.provider.id, start_time=self.slot_start, end_time=self.slot_end
        )
        slots = appointment_service.find_available_slots(department_name="Dermatology")
        self.assertNotIn(self.slot_start, [s.start_time for s in slots])

    def test_unknown_department_returns_no_slots(self):
        slots = appointment_service.find_available_slots(department_name="Radiology")
        self.assertEqual(slots, [])


class BookAppointmentTests(AppointmentServiceTestCase):
    def test_books_successfully_within_availability(self):
        appointment = appointment_service.book_appointment(
            patient=self.patient_a, provider_id=self.provider.id, start_time=self.slot_start, end_time=self.slot_end
        )
        self.assertEqual(appointment.status, Appointment.Status.SCHEDULED)
        self.assertEqual(appointment.patient, self.patient_a)

    def test_rejects_double_booking_same_slot(self):
        appointment_service.book_appointment(
            patient=self.patient_a, provider_id=self.provider.id, start_time=self.slot_start, end_time=self.slot_end
        )
        with self.assertRaises(SlotUnavailableError):
            appointment_service.book_appointment(
                patient=self.patient_b, provider_id=self.provider.id, start_time=self.slot_start, end_time=self.slot_end
            )

    def test_rejects_booking_outside_availability_window(self):
        far_future = self.availability.end_time + timedelta(days=5)
        with self.assertRaises(SlotUnavailableError):
            appointment_service.book_appointment(
                patient=self.patient_a,
                provider_id=self.provider.id,
                start_time=far_future,
                end_time=far_future + timedelta(minutes=30),
            )

    def test_rejects_booking_in_the_past(self):
        past = timezone.now() - timedelta(days=1)
        with self.assertRaises(InvalidAppointmentRequestError):
            appointment_service.book_appointment(
                patient=self.patient_a, provider_id=self.provider.id, start_time=past, end_time=past + timedelta(minutes=30)
            )

    def test_rejects_unknown_provider(self):
        with self.assertRaises(InvalidAppointmentRequestError):
            appointment_service.book_appointment(
                patient=self.patient_a, provider_id=999999, start_time=self.slot_start, end_time=self.slot_end
            )

    def test_rejects_inactive_provider(self):
        self.provider.active = False
        self.provider.save()
        with self.assertRaises(InvalidAppointmentRequestError):
            appointment_service.book_appointment(
                patient=self.patient_a, provider_id=self.provider.id, start_time=self.slot_start, end_time=self.slot_end
            )


class CancelAppointmentTests(AppointmentServiceTestCase):
    def setUp(self):
        super().setUp()
        self.appointment = appointment_service.book_appointment(
            patient=self.patient_a, provider_id=self.provider.id, start_time=self.slot_start, end_time=self.slot_end
        )

    def test_owner_can_cancel(self):
        cancelled = appointment_service.cancel_appointment(patient=self.patient_a, appointment_id=self.appointment.id)
        self.assertEqual(cancelled.status, Appointment.Status.CANCELLED)

    def test_non_owner_cannot_cancel(self):
        with self.assertRaises(NotOwnerError):
            appointment_service.cancel_appointment(patient=self.patient_b, appointment_id=self.appointment.id)

    def test_cancelling_already_cancelled_appointment_rejected(self):
        appointment_service.cancel_appointment(patient=self.patient_a, appointment_id=self.appointment.id)
        with self.assertRaises(InvalidAppointmentRequestError):
            appointment_service.cancel_appointment(patient=self.patient_a, appointment_id=self.appointment.id)

    def test_cancelling_nonexistent_appointment_rejected(self):
        with self.assertRaises(AppointmentNotFoundError):
            appointment_service.cancel_appointment(patient=self.patient_a, appointment_id=999999)

    def test_cancelled_slot_becomes_available_again(self):
        appointment_service.cancel_appointment(patient=self.patient_a, appointment_id=self.appointment.id)
        slots = appointment_service.find_available_slots(department_name="Dermatology")
        self.assertIn(self.slot_start, [s.start_time for s in slots])


class RescheduleAppointmentTests(AppointmentServiceTestCase):
    def setUp(self):
        super().setUp()
        self.appointment = appointment_service.book_appointment(
            patient=self.patient_a, provider_id=self.provider.id, start_time=self.slot_start, end_time=self.slot_end
        )
        self.new_start = self.slot_start + timedelta(minutes=30)
        self.new_end = self.new_start + timedelta(minutes=30)

    def test_owner_can_reschedule_to_open_slot(self):
        updated = appointment_service.reschedule_appointment(
            patient=self.patient_a, appointment_id=self.appointment.id, new_start_time=self.new_start, new_end_time=self.new_end
        )
        self.assertEqual(updated.start_time, self.new_start)
        self.assertEqual(updated.id, self.appointment.id)  # same row, not delete+recreate

    def test_non_owner_cannot_reschedule(self):
        with self.assertRaises(NotOwnerError):
            appointment_service.reschedule_appointment(
                patient=self.patient_b, appointment_id=self.appointment.id, new_start_time=self.new_start, new_end_time=self.new_end
            )

    def test_cannot_reschedule_into_a_taken_slot(self):
        appointment_service.book_appointment(
            patient=self.patient_b, provider_id=self.provider.id, start_time=self.new_start, end_time=self.new_end
        )
        with self.assertRaises(SlotUnavailableError):
            appointment_service.reschedule_appointment(
                patient=self.patient_a, appointment_id=self.appointment.id, new_start_time=self.new_start, new_end_time=self.new_end
            )

    def test_original_slot_freed_after_successful_reschedule(self):
        appointment_service.reschedule_appointment(
            patient=self.patient_a, appointment_id=self.appointment.id, new_start_time=self.new_start, new_end_time=self.new_end
        )
        slots = appointment_service.find_available_slots(department_name="Dermatology")
        self.assertIn(self.slot_start, [s.start_time for s in slots])


class GetPatientAppointmentsTests(AppointmentServiceTestCase):
    def test_only_returns_own_appointments(self):
        appointment_service.book_appointment(
            patient=self.patient_a, provider_id=self.provider.id, start_time=self.slot_start, end_time=self.slot_end
        )
        appointments_a = appointment_service.get_patient_appointments(patient=self.patient_a)
        appointments_b = appointment_service.get_patient_appointments(patient=self.patient_b)
        self.assertEqual(len(appointments_a), 1)
        self.assertEqual(len(appointments_b), 0)
