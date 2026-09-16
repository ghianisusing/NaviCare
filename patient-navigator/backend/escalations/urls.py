from django.urls import path

from .views import (
    EscalationAssignView,
    EscalationDetailView,
    EscalationListView,
    EscalationRespondView,
    EscalationResolveView,
)

app_name = "escalations"

urlpatterns = [
    path("escalations/", EscalationListView.as_view(), name="escalation-list"),
    path("escalations/<int:pk>/", EscalationDetailView.as_view(), name="escalation-detail"),
    path("escalations/<int:pk>/assign/", EscalationAssignView.as_view(), name="escalation-assign"),
    path("escalations/<int:pk>/resolve/", EscalationResolveView.as_view(), name="escalation-resolve"),
    path("escalations/<int:pk>/respond/", EscalationRespondView.as_view(), name="escalation-respond"),
]
