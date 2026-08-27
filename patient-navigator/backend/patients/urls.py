from django.urls import path

from .views import MyPatientProfileView

app_name = "patients"

urlpatterns = [
    path("me/", MyPatientProfileView.as_view(), name="me"),
]
