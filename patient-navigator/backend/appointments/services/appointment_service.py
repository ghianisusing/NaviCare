"""
Appointment Service — the single source of truth for appointment
business logic.

Both the REST API (appointments/views.py) and the agent tool layer
(tools/appointment_tools.py) call into this module rather than
duplicating query/validation logic — see the Phase 4 architectural
principle: "Agents decide what needs to happen; backend services decide
whether and how it happens." Nothing here trusts an LLM-supplied value
without re-validating it against the database.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date as date_type
from datetime import datetime, timedelta

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from patients.models import Patient

from ..models import Appointment, Availability, Department, Provider
from .exceptions import (
    AppointmentNotFoundError,
    InvalidAppointmentRequestError,
    NotOwnerError,
    SlotUnavailableError,
)

SLOT_DURATION_MINUTES = 30


@dataclass
class Slot:
    provider_id: int
    provider_name: str
    department_name: str
    start_time: datetime
    end_time: datetime


# ---------------------------------------------------------------------------
# Read-only search
# ---------------------------------------------------------------------------


def search_departments(query: str = "") -> list[Department]:
    queryset = Department.objects.all()
    if query:
        queryset = queryset.filter(name__icontains=query)
    return list(queryset)


def search_providers(*, department_id: int | None = None, department_name: str = "", query: str = "") -> list[Provider]:
    queryset = Provider.objects.filter(active=True).select_related("department")
    if department_id is not None:
        queryset = queryset.filter(department_id=department_id)
    if department_name:
        queryset = queryset.filter(department__name__icontains=department_name)
    if query:
        queryset = queryset.filter(Q(first_name__icontains=query) | Q(last_name__icontains=query))
    return list(queryset)


def find_available_slots(
    *,
    department_id: int | None = None,
    department_name: str = "",
    provider_id: int | None = None,
    on_date: date_type | None = None,
    days_ahead: int = 14,
    limit: int = 10,
) -> list[Slot]:
    """Derive concrete bookable slots from Availability windows, minus
    whatever is already booked. Slots are fixed-length
    (SLOT_DURATION_MINUTES) so a provider/start_time pair can be booked
    with a simple database-level uniqueness guarantee — see
    Appointment.Meta.constraints.
    """
    providers = search_providers(department_id=department_id, department_name=department_name)
    if provider_id is not None:
        providers = [p for p in providers if p.id == provider_id]
    if not providers:
        return []

    now = timezone.now()
    window_end = now + timedelta(days=days_ahead)

    availability_qs = Availability.objects.filter(
        provider__in=providers, is_available=True, end_time__gt=now, start_time__lt=window_end
    ).select_related("provider", "provider__department")

    if on_date is not None:
        availability_qs = availability_qs.filter(start_time__date=on_date)

    booked_starts = set(
        Appointment.objects.filter(
            provider__in=providers, status=Appointment.Status.SCHEDULED
        ).values_list("provider_id", "start_time")
    )

    slots: list[Slot] = []
    for window in availability_qs.order_by("start_time"):
        cursor = window.start_time
        while cursor + timedelta(minutes=SLOT_DURATION_MINUTES) <= window.end_time:
            slot_end = cursor + timedelta(minutes=SLOT_DURATION_MINUTES)
            if cursor > now and (window.provider_id, cursor) not in booked_starts:
                slots.append(
                    Slot(
                        provider_id=window.provider_id,
                        provider_name=window.provider.display_name,
                        department_name=window.provider.department.name,
                        start_time=cursor,
                        end_time=slot_end,
                    )
                )
                if len(slots) >= limit:
                    return slots
            cursor = slot_end

    return slots


def get_patient_appointments(*, patient: Patient, status: str | None = None) -> list[Appointment]:
    queryset = Appointment.objects.filter(patient=patient).select_related("provider", "provider__department")
    if status:
        queryset = queryset.filter(status=status)
    return list(queryset)


# ---------------------------------------------------------------------------
# Mutating operations — always re-validate against the database, never
# trust that a caller-supplied slot/appointment is still valid.
# ---------------------------------------------------------------------------


@transaction.atomic
def book_appointment(*, patient: Patient, provider_id: int, start_time: datetime, end_time: datetime, reason: str = "") -> Appointment:
    if end_time <= start_time:
        raise InvalidAppointmentRequestError("end_time must be after start_time.")
    if start_time <= timezone.now():
        raise InvalidAppointmentRequestError("Cannot book an appointment in the past.")

    try:
        provider = Provider.objects.select_for_update().get(pk=provider_id, active=True)
    except Provider.DoesNotExist as exc:
        raise InvalidAppointmentRequestError("Unknown or inactive provider.") from exc

    # Row-level lock + a fresh availability/conflict check inside the
    # transaction — the frontend's/agent's idea of "this slot is open"
    # may be stale by the time this actually runs.
    within_availability = Availability.objects.filter(
        provider=provider, is_available=True, start_time__lte=start_time, end_time__gte=end_time
    ).exists()
    if not within_availability:
        raise SlotUnavailableError("That slot is outside the provider's availability.")

    already_booked = Appointment.objects.select_for_update().filter(
        provider=provider, start_time=start_time, status=Appointment.Status.SCHEDULED
    ).exists()
    if already_booked:
        raise SlotUnavailableError("That slot was just booked by someone else.")

    # The UniqueConstraint on (provider, start_time) WHERE status='scheduled'
    # is the final backstop if two requests somehow race past the checks
    # above — see Appointment.Meta.constraints.
    return Appointment.objects.create(
        patient=patient, provider=provider, start_time=start_time, end_time=end_time, reason=reason
    )


def _get_owned_appointment(*, patient: Patient, appointment_id: int) -> Appointment:
    try:
        appointment = Appointment.objects.select_related("provider").get(pk=appointment_id)
    except Appointment.DoesNotExist as exc:
        raise AppointmentNotFoundError("No appointment found with that id.") from exc

    if appointment.patient_id != patient.id:
        # Deliberately the same exception/message as "not found" at the
        # call sites that expose this to the patient — never confirm
        # that an id belongs to someone else.
        raise NotOwnerError("This appointment does not belong to the requesting patient.")

    return appointment


# Public alias — used both internally and by the agent layer
# (agents/appointment/service.py) to pre-check ownership before
# proposing a cancel/reschedule action. Read-only; safe to call outside
# a transaction.
get_owned_appointment = _get_owned_appointment


@transaction.atomic
def cancel_appointment(*, patient: Patient, appointment_id: int) -> Appointment:
    appointment = _get_owned_appointment(patient=patient, appointment_id=appointment_id)

    if appointment.status != Appointment.Status.SCHEDULED:
        raise InvalidAppointmentRequestError("Only a scheduled appointment can be cancelled.")

    appointment.status = Appointment.Status.CANCELLED
    appointment.save(update_fields=["status", "updated_at"])
    return appointment


@transaction.atomic
def reschedule_appointment(*, patient: Patient, appointment_id: int, new_start_time: datetime, new_end_time: datetime) -> Appointment:
    if new_end_time <= new_start_time:
        raise InvalidAppointmentRequestError("end_time must be after start_time.")
    if new_start_time <= timezone.now():
        raise InvalidAppointmentRequestError("Cannot reschedule to a time in the past.")

    appointment = _get_owned_appointment(patient=patient, appointment_id=appointment_id)
    if appointment.status != Appointment.Status.SCHEDULED:
        raise InvalidAppointmentRequestError("Only a scheduled appointment can be rescheduled.")

    provider = Provider.objects.select_for_update().get(pk=appointment.provider_id)

    within_availability = Availability.objects.filter(
        provider=provider, is_available=True, start_time__lte=new_start_time, end_time__gte=new_end_time
    ).exists()
    if not within_availability:
        raise SlotUnavailableError("That slot is outside the provider's availability.")

    conflict = (
        Appointment.objects.select_for_update()
        .filter(provider=provider, start_time=new_start_time, status=Appointment.Status.SCHEDULED)
        .exclude(pk=appointment.pk)
        .exists()
    )
    if conflict:
        raise SlotUnavailableError("That slot was just booked by someone else.")

    # Update the existing row in place — the original booking is never
    # dropped before the new time is confirmed available, since this is
    # a single atomic update rather than delete-then-recreate.
    appointment.start_time = new_start_time
    appointment.end_time = new_end_time
    appointment.save(update_fields=["start_time", "end_time", "updated_at"])
    return appointment
