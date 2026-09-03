"""Read-only notification list + mark-as-read — every query is scoped
to the requesting patient (see PatientScopedNotificationMixin)."""

from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from patients.models import Patient

from .models import Notification
from .serializers import NotificationSerializer


class PatientScopedNotificationMixin:
    def get_patient(self) -> Patient:
        return get_object_or_404(Patient, user=self.request.user)


class NotificationListView(PatientScopedNotificationMixin, generics.ListAPIView):
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        queryset = Notification.objects.filter(patient=self.get_patient())
        unread_only = self.request.query_params.get("unread")
        if unread_only:
            queryset = queryset.filter(read=False)
        return queryset


class NotificationMarkReadView(PatientScopedNotificationMixin, APIView):
    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request, pk):
        try:
            notification = Notification.objects.get(pk=pk, patient=self.get_patient())
        except Notification.DoesNotExist:
            return Response({"error": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        if not notification.read:
            notification.read = True
            notification.read_at = timezone.now()
            notification.save(update_fields=["read", "read_at"])

        return Response(NotificationSerializer(notification).data)
