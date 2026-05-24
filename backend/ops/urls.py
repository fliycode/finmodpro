"""
Ops 应用的 URL 路由配置。
类比 SpringBoot: 相当于 @RestController 中的 @RequestMapping 路径映射，
将 HTTP 请求路径分发到对应的控制器视图。

路由分为三组:
- /monitoring/status  - 系统状态概览
- /monitoring/metrics  - 指标时序数据
- /alerts/rules       - 告警规则 CRUD
- /alerts/events      - 告警事件列表与确认
"""

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
    # === 系统监控 ===
    # GET /api/ops/monitoring/status - 获取当前系统状态概览
    path("monitoring/status", SystemStatusView.as_view(), name="monitoring-status-legacy"),
    path("monitoring/status/", SystemStatusView.as_view(), name="monitoring-status"),
    # GET /api/ops/monitoring/metrics - 获取指标时序数据
    path("monitoring/metrics", MetricTimeSeriesView.as_view(), name="metric-timeseries-legacy"),
    path("monitoring/metrics/", MetricTimeSeriesView.as_view(), name="metric-timeseries"),

    # === 告警规则 ===
    # GET  /api/ops/alerts/rules - 获取告警规则列表
    # POST /api/ops/alerts/rules - 创建告警规则
    path("alerts/rules", AlertRuleListView.as_view(), name="alert-rule-list-legacy"),
    path("alerts/rules/", AlertRuleListView.as_view(), name="alert-rule-list"),
    # POST /api/ops/alerts/rules/seed-defaults - 播种默认告警规则
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
    # GET / PATCH / DELETE /api/ops/alerts/rules/{rule_id} - 单条告警规则 CRUD
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

    # === 告警事件 ===
    # GET /api/ops/alerts/events - 获取告警事件列表
    path("alerts/events", AlertEventListView.as_view(), name="alert-event-list-legacy"),
    path("alerts/events/", AlertEventListView.as_view(), name="alert-event-list"),
    # POST /api/ops/alerts/events/{event_id}/acknowledge - 确认告警事件
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
