from django.urls import path

from .views import (
    AgentActionConfirmView,
    AgentActionDeclineView,
    AppointmentDetailView,
    AppointmentListCreateView,
    AvailableSlotsView,
    DepartmentListView,
    ProviderListView,
)

app_name = "appointments"

urlpatterns = [
    path("departments/", DepartmentListView.as_view(), name="department-list"),
    path("providers/", ProviderListView.as_view(), name="provider-list"),
    path("appointments/available-slots/", AvailableSlotsView.as_view(), name="available-slots"),
    path("appointments/", AppointmentListCreateView.as_view(), name="appointment-list-create"),
    path("appointments/<int:pk>/", AppointmentDetailView.as_view(), name="appointment-detail"),
    path("appointments/agent-actions/<int:pk>/confirm/", AgentActionConfirmView.as_view(), name="agent-action-confirm"),
    path("appointments/agent-actions/<int:pk>/decline/", AgentActionDeclineView.as_view(), name="agent-action-decline"),
]
