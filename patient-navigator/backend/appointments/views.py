"""
Direct REST API for appointment management — the second of the two
ways a patient can manage appointments (the other being the
conversational Appointment Agent). Both funnel into the same
`appointments.services.appointment_service` module, per the Phase 4
principle of a single service layer shared by the API and the agent
tools.

Booking/rescheduling/cancelling here execute immediately (no separate
confirmation step at the API level — a native "are you sure?" is a
frontend UI concern). The agent/chat path is different: there, a
mutating action is only ever *proposed* and requires hitting
AgentActionConfirmView before anything executes — see
agents/appointment/service.py.
"""

from __future__ import annotations

from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from patients.models import Patient

from .models import AgentAction, Appointment, Department, Provider
from .serializers import (
    AgentActionSerializer,
    AppointmentCreateSerializer,
    AppointmentSerializer,
    DepartmentSerializer,
    ProviderSerializer,
    RescheduleSerializer,
)
from .services import appointment_service
from .services.exceptions import AppointmentError, AppointmentNotFoundError, NotOwnerError, SlotUnavailableError


class DepartmentListView(generics.ListAPIView):
    """GET /api/departments/ — read-only, any authenticated patient."""

    queryset = Department.objects.all()
    serializer_class = DepartmentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        query = self.request.query_params.get("query", "")
        return appointment_service.search_departments(query=query)


class ProviderListView(generics.ListAPIView):
    """GET /api/providers/?department=&query= — read-only."""

    serializer_class = ProviderSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        department_name = self.request.query_params.get("department", "")
        query = self.request.query_params.get("query", "")
        return appointment_service.search_providers(department_name=department_name, query=query)


class AvailableSlotsView(APIView):
    """GET /api/appointments/available-slots/?department=&provider=&date="""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        department_name = request.query_params.get("department", "")
        provider_id = request.query_params.get("provider")
        date_str = request.query_params.get("date")

        on_date = None
        if date_str:
            from datetime import date as date_type

            try:
                on_date = date_type.fromisoformat(date_str)
            except ValueError:
                return Response({"error": "Invalid date format, expected YYYY-MM-DD."}, status=status.HTTP_400_BAD_REQUEST)

        slots = appointment_service.find_available_slots(
            department_name=department_name,
            provider_id=int(provider_id) if provider_id else None,
            on_date=on_date,
        )
        return Response(
            [
                {
                    "provider_id": s.provider_id,
                    "provider_name": s.provider_name,
                    "department_name": s.department_name,
                    "start_time": s.start_time.isoformat(),
                    "end_time": s.end_time.isoformat(),
                }
                for s in slots
            ]
        )


class PatientScopedAppointmentMixin:
    def get_patient(self) -> Patient:
        return get_object_or_404(Patient, user=self.request.user)


class AppointmentListCreateView(PatientScopedAppointmentMixin, generics.ListCreateAPIView):
    """
    GET  /api/appointments/  — the current patient's own appointments
    POST /api/appointments/  — book directly (no chat/agent involved)
    """

    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        status_filter = self.request.query_params.get("status")
        return appointment_service.get_patient_appointments(patient=self.get_patient(), status=status_filter)

    def get_serializer_class(self):
        return AppointmentCreateSerializer if self.request.method == "POST" else AppointmentSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            appointment = appointment_service.book_appointment(
                patient=self.get_patient(),
                provider_id=data["provider"],
                start_time=data["start_time"],
                end_time=data["end_time"],
                reason=data.get("reason", ""),
            )
        except SlotUnavailableError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_409_CONFLICT)
        except AppointmentError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(AppointmentSerializer(appointment).data, status=status.HTTP_201_CREATED)


class AppointmentDetailView(PatientScopedAppointmentMixin, APIView):
    """
    GET    /api/appointments/{id}/  — retrieve (own appointments only)
    PATCH  /api/appointments/{id}/  — reschedule
    DELETE /api/appointments/{id}/  — cancel
    """

    permission_classes = [permissions.IsAuthenticated]

    def _get_owned(self, pk):
        try:
            return appointment_service.get_owned_appointment(patient=self.get_patient(), appointment_id=pk)
        except (AppointmentNotFoundError, NotOwnerError):
            # Same response either way — never confirm that an id
            # belongs to someone else.
            return None

    def get(self, request, pk):
        appointment = self._get_owned(pk)
        if appointment is None:
            return Response({"error": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(AppointmentSerializer(appointment).data)

    def patch(self, request, pk):
        if self._get_owned(pk) is None:
            return Response({"error": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        serializer = RescheduleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            appointment = appointment_service.reschedule_appointment(
                patient=self.get_patient(),
                appointment_id=pk,
                new_start_time=serializer.validated_data["start_time"],
                new_end_time=serializer.validated_data["end_time"],
            )
        except SlotUnavailableError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_409_CONFLICT)
        except AppointmentError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(AppointmentSerializer(appointment).data)

    def delete(self, request, pk):
        if self._get_owned(pk) is None:
            return Response({"error": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        try:
            appointment_service.cancel_appointment(patient=self.get_patient(), appointment_id=pk)
        except AppointmentError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(status=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# Agent action confirmation — the only place a proposal from the chat/
# agent path actually executes. See agents/appointment/service.py for
# where a pending AgentAction gets created.
# ---------------------------------------------------------------------------


class AgentActionConfirmView(PatientScopedAppointmentMixin, APIView):
    """POST /api/appointments/agent-actions/{id}/confirm/"""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        patient = self.get_patient()
        try:
            action = AgentAction.objects.get(pk=pk, patient=patient)
        except AgentAction.DoesNotExist:
            return Response({"error": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        if action.status != AgentAction.Status.VALIDATED:
            return Response({"error": "This action can no longer be confirmed."}, status=status.HTTP_409_CONFLICT)

        try:
            result = _execute_agent_action(action)
        except SlotUnavailableError as exc:
            action.status = AgentAction.Status.FAILED
            action.save(update_fields=["status", "updated_at"])
            return Response({"error": str(exc)}, status=status.HTTP_409_CONFLICT)
        except (AppointmentNotFoundError, NotOwnerError) as exc:
            action.status = AgentAction.Status.FAILED
            action.save(update_fields=["status", "updated_at"])
            return Response({"error": str(exc)}, status=status.HTTP_404_NOT_FOUND)
        except AppointmentError as exc:
            action.status = AgentAction.Status.FAILED
            action.save(update_fields=["status", "updated_at"])
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        action.status = AgentAction.Status.EXECUTED
        action.save(update_fields=["status", "updated_at"])
        return Response({"action": AgentActionSerializer(action).data, "appointment": AppointmentSerializer(result).data})


class AgentActionDeclineView(PatientScopedAppointmentMixin, APIView):
    """POST /api/appointments/agent-actions/{id}/decline/"""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        patient = self.get_patient()
        try:
            action = AgentAction.objects.get(pk=pk, patient=patient)
        except AgentAction.DoesNotExist:
            return Response({"error": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        if action.status != AgentAction.Status.VALIDATED:
            return Response({"error": "This action can no longer be declined."}, status=status.HTTP_409_CONFLICT)

        action.status = AgentAction.Status.DECLINED
        action.save(update_fields=["status", "updated_at"])
        return Response({"action": AgentActionSerializer(action).data})


def _execute_agent_action(action: AgentAction) -> Appointment:
    """Re-parse the stored (already-validated-shape) arguments and run
    the real, transaction-safe service call — this is where a slot that
    became unavailable between proposal and confirmation is caught."""
    from datetime import datetime

    args = action.arguments

    if action.tool_name == "book_appointment":
        return appointment_service.book_appointment(
            patient=action.patient,
            provider_id=args["provider_id"],
            start_time=datetime.fromisoformat(args["start_time"]),
            end_time=datetime.fromisoformat(args["end_time"]),
            reason=args.get("reason", ""),
        )
    if action.tool_name == "cancel_appointment":
        return appointment_service.cancel_appointment(patient=action.patient, appointment_id=args["appointment_id"])
    if action.tool_name == "reschedule_appointment":
        return appointment_service.reschedule_appointment(
            patient=action.patient,
            appointment_id=args["appointment_id"],
            new_start_time=datetime.fromisoformat(args["new_start_time"]),
            new_end_time=datetime.fromisoformat(args["new_end_time"]),
        )
    raise AppointmentError("Unsupported action.")
