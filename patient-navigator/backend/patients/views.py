from rest_framework import generics, permissions

from .models import Patient
from .serializers import PatientSerializer


class MyPatientProfileView(generics.RetrieveUpdateAPIView):
    """GET/PATCH /api/patients/me/

    Always resolves to the *requesting* user's own Patient row — there is
    no id in the URL to tamper with, which is what keeps Patient A from
    ever being able to reach Patient B's profile.
    """

    serializer_class = PatientSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        patient, _ = Patient.objects.get_or_create(
            user=self.request.user,
            defaults={
                "first_name": self.request.user.first_name or "",
                "last_name": self.request.user.last_name or "",
            },
        )
        return patient
