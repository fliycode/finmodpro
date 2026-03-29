from django.urls import path

from systemcheck.controllers.dashboard_controller import DashboardStatsView
from systemcheck.controllers.health_controller import HealthView


urlpatterns = [
    path("dashboard/stats", DashboardStatsView.as_view(), name="dashboard-stats-legacy"),
    path("dashboard/stats/", DashboardStatsView.as_view(), name="dashboard-stats"),
    path("health", HealthView.as_view(), name="health-legacy"),
    path("health/", HealthView.as_view(), name="health"),
]
