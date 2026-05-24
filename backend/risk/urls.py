"""
Risk 应用的 URL 路由配置。
类比 SpringBoot: 相当于 @RestController 中的 @RequestMapping 路径映射，
将 HTTP 请求路径分发到对应的控制器视图。

路由分组:
- /analytics/overview              - 风险分析概览
- /events                           - 风险事件列表
- /events/{event_id}/review         - 风险事件审核
- /reports/company                  - 公司报告（创建）
- /reports/time-range               - 时间区间报告（创建）
- /reports/{report_id}/export       - 报告导出
- /documents/{document_id}/extract  - 单文档风险抽取
- /documents/{document_id}/report   - 单文档报告（创建）
- /documents/extract-batch          - 批量文档风险抽取
- /sentiment/analyze                - 舆情分析
"""

from django.urls import path

from risk.controllers import (
    CompanyRiskReportCreateView,
    DocumentRiskReportCreateView,
    RiskAnalyticsOverviewView,
    RiskDocumentBatchExtractRetryView,
    RiskDocumentBatchExtractView,
    RiskDocumentExtractRetryView,
    RiskDocumentExtractView,
    RiskEventListView,
    RiskEventReviewView,
    RiskExtractStatusView,
    RiskReportExportView,
    SentimentAnalyzeView,
    TimeRangeRiskReportCreateView,
)


urlpatterns = [
    # 风险分析概览仪表盘
    path("analytics/overview", RiskAnalyticsOverviewView.as_view(), name="risk-analytics-overview"),
    # 风险事件列表查询
    path("events", RiskEventListView.as_view(), name="risk-event-list"),
    # 风险事件审核
    path("events/<int:event_id>/review", RiskEventReviewView.as_view(), name="risk-event-review"),
    # 公司维度风险报告（创建）
    path("reports/company", CompanyRiskReportCreateView.as_view(), name="risk-report-company-create"),
    # 报告导出（Markdown / JSON）
    path("reports/<int:report_id>/export", RiskReportExportView.as_view(), name="risk-report-export"),
    # 时间区间风险报告（创建）
    path("reports/time-range", TimeRangeRiskReportCreateView.as_view(), name="risk-report-time-range-create"),
    # 舆情分析
    path("sentiment/analyze", SentimentAnalyzeView.as_view(), name="risk-sentiment-analyze"),
    # 批量文档风险抽取
    path(
        "documents/extract-batch",
        RiskDocumentBatchExtractView.as_view(),
        name="risk-document-batch-extract",
    ),
    # 批量文档风险抽取重试
    path(
        "documents/extract-batch/retry",
        RiskDocumentBatchExtractRetryView.as_view(),
        name="risk-document-batch-extract-retry",
    ),
    # 风险抽取任务状态查询
    path(
        "documents/extract/status/<str:task_id>",
        RiskExtractStatusView.as_view(),
        name="risk-extract-status",
    ),
    # 单文档风险抽取
    path(
        "documents/<int:document_id>/extract",
        RiskDocumentExtractView.as_view(),
        name="risk-document-extract",
    ),
    # 单文档风险报告（创建）
    path(
        "documents/<int:document_id>/report",
        DocumentRiskReportCreateView.as_view(),
        name="risk-document-report-create",
    ),
    # 单文档风险抽取重试
    path(
        "documents/<int:document_id>/extract/retry",
        RiskDocumentExtractRetryView.as_view(),
        name="risk-document-extract-retry",
    ),
]
