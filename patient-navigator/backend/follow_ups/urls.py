from django.urls import path

from .views import (
    AppointmentReminderView,
    FollowUpDetailView,
    FollowUpListCreateView,
    ReminderDetailView,
    ReminderListCreateView,
)

app_name = "follow_ups"

urlpatterns = [
    path("follow-ups/", FollowUpListCreateView.as_view(), name="follow-up-list-create"),
    path("follow-ups/<int:pk>/", FollowUpDetailView.as_view(), name="follow-up-detail"),
    path("follow-ups/appointment-reminder/", AppointmentReminderView.as_view(), name="appointment-reminder"),
    path("reminders/", ReminderListCreateView.as_view(), name="reminder-list-create"),
    path("reminders/<int:pk>/", ReminderDetailView.as_view(), name="reminder-detail"),
]
