"""
Admin-only knowledge management API.

Patients never access this directly — they only ever retrieve knowledge
indirectly through the Information Agent (knowledge/retrieval.py called
from agents/information/). `IsAdminUser` (request.user.is_staff) gates
every view here.
"""

from rest_framework import generics, permissions

from .ingestion import ingest_all
from .models import HealthcareDocument
from .serializers import HealthcareDocumentSerializer
from rest_framework.response import Response
from rest_framework.views import APIView


class HealthcareDocumentListCreateView(generics.ListCreateAPIView):
    queryset = HealthcareDocument.objects.all()
    serializer_class = HealthcareDocumentSerializer
    permission_classes = [permissions.IsAdminUser]

    def perform_create(self, serializer):
        from .services import create_document

        create_document(**serializer.validated_data)


class HealthcareDocumentDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = HealthcareDocument.objects.all()
    serializer_class = HealthcareDocumentSerializer
    permission_classes = [permissions.IsAdminUser]

    def perform_update(self, serializer):
        from .services import update_document

        update_document(serializer.instance, **serializer.validated_data)


class TriggerIngestionView(APIView):
    """POST /api/knowledge/ingest/ — re-chunk and re-embed every document."""

    permission_classes = [permissions.IsAdminUser]

    def post(self, request):
        results = ingest_all()
        return Response({"ingested": results})
