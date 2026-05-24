"""
Ops services 包，汇集所有运维监控相关的业务逻辑服务。
类比 SpringBoot: 相当于 @Service 层的包目录，导出所有公共服务接口。

模块分为三类:
- metrics_collector_service: 系统指标采集（CPU、内存、磁盘、服务健康检测）
- alert_engine_service:      告警引擎（规则评估、事件确认）
- monitoring_query_service:  监控查询（状态概览、时序数据、规则/事件的 CRUD）
"""

from ops.services.metrics_collector_service import (
    collect_system_metrics,
    store_metrics,
)
from ops.services.alert_engine_service import (
    acknowledge_alert_event,
    evaluate_alert_rules,
)
from ops.services.monitoring_query_service import (
    acknowledge_event,
    create_alert_rule,
    delete_alert_rule,
    get_alert_rule,
    get_current_system_status,
    get_metric_time_series,
    list_alert_events,
    list_alert_rules,
    seed_default_alert_rules,
    update_alert_rule,
)

__all__ = [
    "collect_system_metrics",
    "store_metrics",
    "evaluate_alert_rules",
    "acknowledge_alert_event",
    "get_current_system_status",
    "get_metric_time_series",
    "list_alert_rules",
    "get_alert_rule",
    "create_alert_rule",
    "seed_default_alert_rules",
    "update_alert_rule",
    "delete_alert_rule",
    "list_alert_events",
    "acknowledge_event",
]
