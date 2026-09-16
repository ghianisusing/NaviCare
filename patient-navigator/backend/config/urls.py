from django.contrib import admin
from django.urls import include, path
from rest_framework_simplejwt.views import TokenRefreshView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/auth/", include("users.urls")),
    path("api/auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("api/patients/", include("patients.urls")),
    path("api/conversations/", include("conversations.urls")),
    path("api/knowledge/", include("knowledge.urls")),
    path("api/", include("appointments.urls")),
    path("api/", include("follow_ups.urls")),
    path("api/", include("notifications.urls")),
    path("api/", include("escalations.urls")),
    path("api/", include("observability.urls")),
]
