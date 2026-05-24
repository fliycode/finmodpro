"""
Systemcheck 控制器包 —— 汇聚所有系统巡检相关的 HTTP 端点。

类比 SpringBoot: 相当于 @RestController 包的集中导出 (package-info.java)，
统一对外暴露 AuditLogListView、DashboardStatsView、HealthView 三个视图。

模块组成:
- audit_controller:     审计日志查询
- dashboard_controller: 管理仪表盘
- health_controller:    系统健康检查
"""
from systemcheck.controllers.audit_controller import AuditLogListView
from systemcheck.controllers.dashboard_controller import DashboardStatsView
from systemcheck.controllers.health_controller import HealthView

__all__ = [
    "AuditLogListView",
    "DashboardStatsView",
    "HealthView",
]
