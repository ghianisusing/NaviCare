"""
Admin-only knowledge management API.

Patients never access this directly — they only ever retrieve knowledge
indirectly through the Information Agent (knowledge/retrieval.py called
from agents/information/). `IsAdminUser` (request.user.is_staff) gates
every view here.
"""

from rest_framework import generics, permissions
from rest_framework.exceptions import APIException
from rest_framework.response import Response
from rest_framework.views import APIView

from .embeddings import EmbeddingError
from .ingestion import ingest_all
from .models import HealthcareDocument
from .serializers import HealthcareDocumentSerializer


class EmbeddingServiceUnavailable(APIException):
    status_code = 503
    default_detail = "The embedding service is unavailable. Try again shortly."
    default_code = "embedding_unavailable"


class HealthcareDocumentListCreateView(generics.ListCreateAPIView):
    queryset = HealthcareDocument.objects.all()
    serializer_class = HealthcareDocumentSerializer
    permission_classes = [permissions.IsAdminUser]

    def perform_create(self, serializer):
        from .services import create_document

        try:
            create_document(**serializer.validated_data)
        except EmbeddingError as exc:
            raise EmbeddingServiceUnavailable() from exc


class HealthcareDocumentDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = HealthcareDocument.objects.all()
    serializer_class = HealthcareDocumentSerializer
    permission_classes = [permissions.IsAdminUser]

    def perform_update(self, serializer):
        from .services import update_document

        try:
            update_document(serializer.instance, **serializer.validated_data)
        except EmbeddingError as exc:
            raise EmbeddingServiceUnavailable() from exc


class TriggerIngestionView(APIView):
    """POST /api/knowledge/ingest/ — re-chunk and re-embed every document."""

    permission_classes = [permissions.IsAdminUser]

    def post(self, request):
        try:
            results = ingest_all()
        except EmbeddingError as exc:
            raise EmbeddingServiceUnavailable() from exc
        return Response({"ingested": results})
