from django.urls import path

from .views import AgentMetricsView, AgentTraceDetailView, AgentTraceListView

app_name = "observability"

urlpatterns = [
    path("agent-traces/", AgentTraceListView.as_view(), name="trace-list"),
    path("agent-traces/<int:pk>/", AgentTraceDetailView.as_view(), name="trace-detail"),
    path("agent-metrics/", AgentMetricsView.as_view(), name="agent-metrics"),
]
