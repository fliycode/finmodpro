"""
Systemcheck 应用的 URL 路由配置。

类比 SpringBoot: 相当于 @RequestMapping 的统一注册中心，
将 HTTP 请求路径映射到对应的控制器视图。

路由映射一览:
- GET /api/systemcheck/audits          -> 审计日志列表
- GET /api/systemcheck/dashboard/stats -> 管理仪表盘统计
- GET /api/systemcheck/health          -> 系统健康检查

说明: 每个路由同时注册带尾部斜杠和不带尾部斜杠两个版本，
以确保前端请求的兼容性。
"""
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
