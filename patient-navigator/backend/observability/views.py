"""
Developer/admin observability API — restricted to `IsSystemAdmin`
(request.user.is_superuser), stricter than the escalation queue's
`IsCareCoordinator`. Per Phase 6 section 39: patients must never reach
AgentTrace or system-wide metrics, and even care coordinators (who
aren't superusers) don't get this — it's system-level monitoring, not
a patient-support tool.
"""

from __future__ import annotations

from django.db.models import Avg, Count, Q
from rest_framework import generics
from rest_framework.response import Response
from rest_framework.views import APIView

from appointments.models import AgentAction
from conversations.models import Conversation
from core.permissions import IsSystemAdmin
from escalations.models import Escalation

from .models import AgentTrace, AgentTraceStep
from .serializers import AgentTraceDetailSerializer, AgentTraceListSerializer


class AgentTraceListView(generics.ListAPIView):
    queryset = AgentTrace.objects.all()
    serializer_class = AgentTraceListSerializer
    permission_classes = [IsSystemAdmin]

    def get_queryset(self):
        queryset = super().get_queryset()
        status_filter = self.request.query_params.get("status")
        final_agent = self.request.query_params.get("final_agent")
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        if final_agent:
            queryset = queryset.filter(final_agent=final_agent)
        return queryset[:200]  # a simple cap rather than full pagination machinery for this scope


class AgentTraceDetailView(generics.RetrieveAPIView):
    queryset = AgentTrace.objects.all()
    serializer_class = AgentTraceDetailSerializer
    permission_classes = [IsSystemAdmin]


class AgentMetricsView(APIView):
    """GET /api/agent-metrics/ — aggregate counts computed from the
    database on request. No caching layer for this scope; the
    aggregation is cheap relative to a portfolio-scale dataset."""

    permission_classes = [IsSystemAdmin]

    def get(self, request):
        trace_counts = AgentTrace.objects.aggregate(
            total=Count("id"),
            completed=Count("id", filter=Q(status=AgentTrace.Status.COMPLETED)),
            failed=Count("id", filter=Q(status=AgentTrace.Status.FAILED)),
            escalated=Count("id", filter=Q(status=AgentTrace.Status.ESCALATED)),
            avg_latency_ms=Avg("total_latency_ms"),
        )

        tool_action_counts = AgentAction.objects.aggregate(
            total=Count("id"),
            failed=Count("id", filter=Q(status__in=[AgentAction.Status.FAILED, AgentAction.Status.REJECTED])),
        )

        # A proxy for retrieval latency: the "information" step's total
        # latency (retrieval + grounded LLM call) — not a separately
        # measured retrieval-only timer, called out explicitly rather
        # than implying more precision than the data actually has.
        avg_information_step_latency_ms = AgentTraceStep.objects.filter(component="information").aggregate(
            avg=Avg("latency_ms")
        )["avg"]

        per_agent = list(
            AgentTrace.objects.exclude(final_agent="")
            .values("final_agent")
            .annotate(count=Count("id"))
            .order_by("-count")
        )

        error_breakdown = list(
            AgentTrace.objects.filter(status=AgentTrace.Status.FAILED)
            .exclude(error_type="")
            .values("error_type")
            .annotate(count=Count("id"))
            .order_by("-count")
        )

        return Response(
            {
                "total_conversations": Conversation.objects.count(),
                "agent_executions": trace_counts["total"] or 0,
                "successful_executions": trace_counts["completed"] or 0,
                "failed_executions": trace_counts["failed"] or 0,
                "escalations": Escalation.objects.count(),
                "escalated_executions": trace_counts["escalated"] or 0,
                "tool_calls": tool_action_counts["total"] or 0,
                "tool_failures": tool_action_counts["failed"] or 0,
                "avg_latency_ms": round(trace_counts["avg_latency_ms"] or 0),
                "avg_information_step_latency_ms": round(avg_information_step_latency_ms or 0),
                "executions_by_agent": per_agent,
                "failures_by_error_type": error_breakdown,
            }
        )
