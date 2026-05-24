"""
Risk services 包，汇集所有风险分析相关的业务逻辑服务。
类比 SpringBoot: 相当于 @Service 层的包目录，导出所有公共服务接口。

模块分为:
- extraction_service:  风险提取（单文档 + 批量）
- adjudication_service: 风险判读与事件增强
- chunk_filter_service: 风险相关切块筛选
- verification_service: 提取-验证循环管道
- query_service:        风险事件查询
- report_service:       风险报告生成与导出
- review_service:       风险事件审核
- sentiment_service:    舆情分析
- task_service:         提取任务生命周期管理
"""

from risk.services.extraction_service import (
    batch_extract_risk_events_for_documents,
    extract_risk_events_for_document,
    list_document_chunks,
)
from risk.services.query_service import list_risk_events
from risk.services.report_service import (
    generate_company_risk_report,
    generate_document_risk_report,
    generate_time_range_risk_report,
)
from risk.services.review_service import review_risk_event
from risk.services.sentiment_service import analyze_sentiment_for_documents

__all__ = [
    "batch_extract_risk_events_for_documents",
    "extract_risk_events_for_document",
    "generate_company_risk_report",
    "generate_document_risk_report",
    "generate_time_range_risk_report",
    "list_document_chunks",
    "list_risk_events",
    "analyze_sentiment_for_documents",
    "review_risk_event",
]
