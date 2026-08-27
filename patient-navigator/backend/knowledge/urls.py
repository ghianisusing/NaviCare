from django.urls import path

from .views import HealthcareDocumentDetailView, HealthcareDocumentListCreateView, TriggerIngestionView

app_name = "knowledge"

urlpatterns = [
    path("documents/", HealthcareDocumentListCreateView.as_view(), name="document-list"),
    path("documents/<int:pk>/", HealthcareDocumentDetailView.as_view(), name="document-detail"),
    path("ingest/", TriggerIngestionView.as_view(), name="ingest"),
]
