"""
Staff-facing escalation queue API. Every endpoint here requires
`IsCareCoordinator` (request.user.is_staff) — patients never see this
directly; they only experience escalation through the conversation
itself (a "Care Support" message eventually appearing) and, per Phase
6's privacy requirements, have no access to the internal queue,
summaries, or other patients' escalations.
"""

from __future__ import annotations

from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from conversations.serializers import MessageSerializer
from core.permissions import IsCareCoordinator

from .models import Escalation
from .serializers import EscalationDetailSerializer, EscalationListSerializer, StaffResponseSerializer
from .services import escalation_service
from .services.exceptions import AlreadyAssignedError, EscalationError, EscalationNotFoundError


class EscalationListView(generics.ListAPIView):
    serializer_class = EscalationListSerializer
    permission_classes = [IsCareCoordinator]

    def get_queryset(self):
        status_filter = self.request.query_params.get("status")
        mine_only = self.request.query_params.get("mine")
        assigned_to_id = self.request.user.id if mine_only else None
        return escalation_service.get_staff_queue(status=status_filter, assigned_to_id=assigned_to_id)


class EscalationDetailView(generics.RetrieveAPIView):
    queryset = Escalation.objects.all()
    serializer_class = EscalationDetailSerializer
    permission_classes = [IsCareCoordinator]


class EscalationAssignView(APIView):
    permission_classes = [IsCareCoordinator]

    def post(self, request, pk):
        try:
            escalation = escalation_service.assign_escalation(staff_user=request.user, escalation_id=pk)
        except EscalationNotFoundError:
            return Response({"error": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        except AlreadyAssignedError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_409_CONFLICT)
        except EscalationError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(EscalationDetailSerializer(escalation).data)


class EscalationResolveView(APIView):
    permission_classes = [IsCareCoordinator]

    def post(self, request, pk):
        try:
            escalation = escalation_service.resolve_escalation(staff_user=request.user, escalation_id=pk)
        except EscalationNotFoundError:
            return Response({"error": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        except EscalationError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(EscalationDetailSerializer(escalation).data)


class EscalationRespondView(APIView):
    """POST /api/escalations/{id}/respond/ — staff sends a message into
    the patient's conversation, persisted with role="staff" so the
    frontend never conflates a human reply with an AI one."""

    permission_classes = [IsCareCoordinator]

    def post(self, request, pk):
        serializer = StaffResponseSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            message = escalation_service.send_staff_response(
                staff_user=request.user, escalation_id=pk, content=serializer.validated_data["content"]
            )
        except EscalationNotFoundError:
            return Response({"error": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        except EscalationError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(MessageSerializer(message).data, status=status.HTTP_201_CREATED)
