"""
Risk controllers 包，汇集所有风险分析相关的控制器视图。
类比 SpringBoot: 相当于 @RestController 类的包目录，
按功能分为分析概览、批量抽取、单文档抽取、事件列表、报告生成、审核和舆情分析。
"""

from risk.controllers.analytics_controller import RiskAnalyticsOverviewView
from risk.controllers.batch_extract_controller import (
    RiskDocumentBatchExtractRetryView,
    RiskDocumentBatchExtractView,
)
from risk.controllers.extract_controller import (
    RiskDocumentExtractRetryView,
    RiskDocumentExtractView,
    RiskExtractStatusView,
)
from risk.controllers.history_controller import RiskExtractionHistoryView
from risk.controllers.list_controller import RiskEventListView
from risk.controllers.report_controller import (
    CompanyRiskReportCreateView,
    DocumentRiskReportCreateView,
    RiskReportExportView,
    TimeRangeRiskReportCreateView,
)
from risk.controllers.review_controller import RiskEventReviewView
from risk.controllers.sentiment_controller import SentimentAnalyzeView

__all__ = [
    "CompanyRiskReportCreateView",
    "DocumentRiskReportCreateView",
    "RiskAnalyticsOverviewView",
    "RiskDocumentBatchExtractRetryView",
    "RiskDocumentBatchExtractView",
    "RiskDocumentExtractRetryView",
    "RiskDocumentExtractView",
    "RiskExtractionHistoryView",
    "RiskExtractStatusView",
    "RiskEventListView",
    "RiskEventReviewView",
    "RiskReportExportView",
    "SentimentAnalyzeView",
    "TimeRangeRiskReportCreateView",
]
