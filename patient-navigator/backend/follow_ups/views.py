"""
Direct REST API for follow-ups and reminders — the second of the two
ways a patient can manage them (the other being the conversational
Follow-Up Agent). Both funnel into follow_ups.services.follow_up_service.

Unlike the agent/chat path, direct API calls to complete/cancel execute
immediately — same convention as appointments/views.py: a native "are
you sure?" is a frontend concern here, not a backend-enforced
confirmation step.
"""

from __future__ import annotations

from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from appointments.models import Appointment
from appointments.serializers import AppointmentSerializer
from patients.models import Patient

from .models import FollowUp, Reminder
from .serializers import (
    AppointmentReminderSerializer,
    FollowUpCreateSerializer,
    FollowUpSerializer,
    ReminderCreateSerializer,
    ReminderSerializer,
)
from .services import follow_up_service
from .services.exceptions import FollowUpError, FollowUpNotFoundError, NotOwnerError, ReminderNotFoundError


class PatientScopedFollowUpMixin:
    def get_patient(self) -> Patient:
        return get_object_or_404(Patient, user=self.request.user)


class FollowUpListCreateView(PatientScopedFollowUpMixin, generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        status_filter = self.request.query_params.get("status")
        return follow_up_service.get_patient_follow_ups(patient=self.get_patient(), status=status_filter)

    def get_serializer_class(self):
        return FollowUpCreateSerializer if self.request.method == "POST" else FollowUpSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        appointment = None
        if data.get("appointment"):
            appointment = get_object_or_404(Appointment, pk=data["appointment"], patient=self.get_patient())

        try:
            follow_up = follow_up_service.create_follow_up(
                patient=self.get_patient(),
                title=data["title"],
                description=data.get("description", ""),
                due_at=data.get("due_at"),
                priority=data.get("priority", FollowUp.Priority.NORMAL),
                appointment=appointment,
            )
        except FollowUpError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(FollowUpSerializer(follow_up).data, status=status.HTTP_201_CREATED)


class FollowUpDetailView(PatientScopedFollowUpMixin, APIView):
    permission_classes = [permissions.IsAuthenticated]

    def _get_owned(self, pk):
        try:
            return follow_up_service.get_owned_follow_up(patient=self.get_patient(), follow_up_id=pk)
        except (FollowUpNotFoundError, NotOwnerError):
            return None

    def get(self, request, pk):
        follow_up = self._get_owned(pk)
        if follow_up is None:
            return Response({"error": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(FollowUpSerializer(follow_up).data)

    def patch(self, request, pk):
        if self._get_owned(pk) is None:
            return Response({"error": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        new_status = request.data.get("status")
        if new_status not in ("completed", "cancelled"):
            return Response({"error": "status must be 'completed' or 'cancelled'."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            if new_status == "completed":
                follow_up = follow_up_service.complete_follow_up(patient=self.get_patient(), follow_up_id=pk)
            else:
                follow_up = follow_up_service.cancel_follow_up(patient=self.get_patient(), follow_up_id=pk)
        except FollowUpError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(FollowUpSerializer(follow_up).data)

    def delete(self, request, pk):
        if self._get_owned(pk) is None:
            return Response({"error": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        try:
            follow_up_service.cancel_follow_up(patient=self.get_patient(), follow_up_id=pk)
        except FollowUpError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(status=status.HTTP_204_NO_CONTENT)


class ReminderListCreateView(PatientScopedFollowUpMixin, generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        status_filter = self.request.query_params.get("status")
        return follow_up_service.get_patient_reminders(patient=self.get_patient(), status=status_filter)

    def get_serializer_class(self):
        return ReminderCreateSerializer if self.request.method == "POST" else ReminderSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            reminder = follow_up_service.create_reminder(
                patient=self.get_patient(), follow_up_id=data["follow_up"], scheduled_for=data["scheduled_for"]
            )
        except FollowUpError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(ReminderSerializer(reminder).data, status=status.HTTP_201_CREATED)


class ReminderDetailView(PatientScopedFollowUpMixin, APIView):
    permission_classes = [permissions.IsAuthenticated]

    def _get_owned(self, pk):
        try:
            return follow_up_service.get_owned_reminder(patient=self.get_patient(), reminder_id=pk)
        except (ReminderNotFoundError, NotOwnerError):
            return None

    def patch(self, request, pk):
        if self._get_owned(pk) is None:
            return Response({"error": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        scheduled_for = request.data.get("scheduled_for")
        if not scheduled_for:
            return Response({"error": "scheduled_for is required."}, status=status.HTTP_400_BAD_REQUEST)

        from rest_framework.fields import DateTimeField

        try:
            parsed = DateTimeField().to_internal_value(scheduled_for)
        except Exception:  # noqa: BLE001
            return Response({"error": "Invalid scheduled_for."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            reminder = follow_up_service.reschedule_reminder(
                patient=self.get_patient(), reminder_id=pk, new_scheduled_for=parsed
            )
        except FollowUpError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(ReminderSerializer(reminder).data)

    def delete(self, request, pk):
        if self._get_owned(pk) is None:
            return Response({"error": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        try:
            follow_up_service.cancel_reminder(patient=self.get_patient(), reminder_id=pk)
        except FollowUpError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(status=status.HTTP_204_NO_CONTENT)


class AppointmentReminderView(PatientScopedFollowUpMixin, APIView):
    """POST /api/follow-ups/appointment-reminder/ — the one-click 'yes,
    remind me' action offered right after booking an appointment (Phase
    5 section 10). Creates a FollowUp + Reminder in one step."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = AppointmentReminderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        patient = self.get_patient()
        appointment = get_object_or_404(Appointment, pk=data["appointment"], patient=patient, status=Appointment.Status.SCHEDULED)

        from datetime import timedelta

        reminder_time = appointment.start_time - timedelta(hours=data["hours_before"])

        try:
            follow_up = follow_up_service.create_follow_up(
                patient=patient,
                title=f"Upcoming appointment with {appointment.provider.display_name}",
                due_at=appointment.start_time,
                appointment=appointment,
            )
            reminder = follow_up_service.create_reminder(
                patient=patient, follow_up_id=follow_up.id, scheduled_for=reminder_time
            )
        except FollowUpError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            {"follow_up": FollowUpSerializer(follow_up).data, "reminder": ReminderSerializer(reminder).data},
            status=status.HTTP_201_CREATED,
        )
