from django.urls import path

from ops.controllers.alert_event_controller import (
    AlertEventAcknowledgeView,
    AlertEventListView,
)
from ops.controllers.alert_rule_controller import (
    AlertRuleDetailView,
    AlertRuleListView,
    AlertRuleSeedDefaultsView,
)
from ops.controllers.metrics_controller import (
    MetricTimeSeriesView,
    SystemStatusView,
)

urlpatterns = [
    path("monitoring/status", SystemStatusView.as_view(), name="monitoring-status-legacy"),
    path("monitoring/status/", SystemStatusView.as_view(), name="monitoring-status"),
    path("monitoring/metrics", MetricTimeSeriesView.as_view(), name="metric-timeseries-legacy"),
    path("monitoring/metrics/", MetricTimeSeriesView.as_view(), name="metric-timeseries"),
    path("alerts/rules", AlertRuleListView.as_view(), name="alert-rule-list-legacy"),
    path("alerts/rules/", AlertRuleListView.as_view(), name="alert-rule-list"),
    path(
        "alerts/rules/seed-defaults",
        AlertRuleSeedDefaultsView.as_view(),
        name="alert-rule-seed-defaults-legacy",
    ),
    path(
        "alerts/rules/seed-defaults/",
        AlertRuleSeedDefaultsView.as_view(),
        name="alert-rule-seed-defaults",
    ),
    path(
        "alerts/rules/<int:rule_id>",
        AlertRuleDetailView.as_view(),
        name="alert-rule-detail-legacy",
    ),
    path(
        "alerts/rules/<int:rule_id>/",
        AlertRuleDetailView.as_view(),
        name="alert-rule-detail",
    ),
    path("alerts/events", AlertEventListView.as_view(), name="alert-event-list-legacy"),
    path("alerts/events/", AlertEventListView.as_view(), name="alert-event-list"),
    path(
        "alerts/events/<int:event_id>/acknowledge",
        AlertEventAcknowledgeView.as_view(),
        name="alert-event-ack-legacy",
    ),
    path(
        "alerts/events/<int:event_id>/acknowledge/",
        AlertEventAcknowledgeView.as_view(),
        name="alert-event-ack",
    ),
]
