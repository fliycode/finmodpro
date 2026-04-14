from django.urls import path

from systemcheck.controllers.audit_controller import AuditLogListView
from systemcheck.controllers.dashboard_controller import DashboardStatsView
from systemcheck.controllers.health_controller import HealthView


urlpatterns = [
    path("audits", AuditLogListView.as_view(), name="audit-log-list-legacy"),
    path("audits/", AuditLogListView.as_view(), name="audit-log-list"),
    path("dashboard/stats", DashboardStatsView.as_view(), name="dashboard-stats-legacy"),
    path("dashboard/stats/", DashboardStatsView.as_view(), name="dashboard-stats"),
    path("health", HealthView.as_view(), name="health-legacy"),
    path("health/", HealthView.as_view(), name="health"),
]
