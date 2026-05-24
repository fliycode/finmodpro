"""
Systemcheck 服务包 —— 汇聚所有系统巡检相关的业务逻辑服务。

类比 SpringBoot: 相当于 @Service 层的包组织，统一对外导出公共服务接口。

模块组成:
- audit_service:     审计日志记录和查询
- dashboard_service: 管理仪表盘数据聚合
- demo_data_service: 演示数据播种
"""
from systemcheck.services.audit_service import list_audit_records, record_audit_event
from systemcheck.services.dashboard_service import get_dashboard_stats

__all__ = ["get_dashboard_stats", "list_audit_records", "record_audit_event"]
