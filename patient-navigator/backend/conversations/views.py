from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from patients.models import Patient

from .models import Conversation
from .serializers import (
    ConversationCreateSerializer,
    ConversationDetailSerializer,
    ConversationListSerializer,
    MessageCreateSerializer,
    MessageSerializer,
)
from .services import chat_service


class PatientScopedMixin:
    """Every queryset here is filtered to request.user's own Patient —
    this is the enforcement point for "Patient A can never reach
    Patient B's conversations", regardless of what id is in the URL."""

    def get_patient(self):
        return get_object_or_404(Patient, user=self.request.user)


class ConversationListCreateView(PatientScopedMixin, generics.ListCreateAPIView):
    """
    GET  /api/conversations/   — list the current patient's conversations
    POST /api/conversations/   — create a new conversation
    """

    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Conversation.objects.filter(patient=self.get_patient())

    def get_serializer_class(self):
        return ConversationCreateSerializer if self.request.method == "POST" else ConversationListSerializer

    def perform_create(self, serializer):
        serializer.save(patient=self.get_patient())


class ConversationDetailView(PatientScopedMixin, generics.RetrieveAPIView):
    """GET /api/conversations/{id}/ — a single conversation with its messages."""

    serializer_class = ConversationDetailSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # Scoping the queryset (not just checking ownership post-fetch)
        # means an out-of-scope id 404s instead of leaking a 403 that
        # would confirm the id exists.
        return Conversation.objects.filter(patient=self.get_patient())


class ConversationMessagesView(PatientScopedMixin, APIView):
    """
    GET  /api/conversations/{id}/messages/ — list messages
    POST /api/conversations/{id}/messages/ — send a message, get the reply
    """

    permission_classes = [permissions.IsAuthenticated]

    def get_conversation(self, pk):
        return get_object_or_404(Conversation, pk=pk, patient=self.get_patient())

    def get(self, request, pk):
        conversation = self.get_conversation(pk)
        messages = conversation.messages.all()
        return Response(MessageSerializer(messages, many=True).data)

    def post(self, request, pk):
        conversation = self.get_conversation(pk)
        serializer = MessageCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        assistant_message = chat_service.send_message(
            conversation=conversation,
            content=serializer.validated_data["content"],
        )
        return Response(MessageSerializer(assistant_message).data, status=status.HTTP_201_CREATED)
