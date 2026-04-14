from django.urls import path

from risk.controllers import (
    CompanyRiskReportCreateView,
    RiskAnalyticsOverviewView,
    RiskDocumentBatchExtractRetryView,
    RiskDocumentBatchExtractView,
    RiskDocumentExtractRetryView,
    RiskDocumentExtractView,
    RiskEventListView,
    RiskEventReviewView,
    RiskReportExportView,
    SentimentAnalyzeView,
    TimeRangeRiskReportCreateView,
)


urlpatterns = [
    path("analytics/overview", RiskAnalyticsOverviewView.as_view(), name="risk-analytics-overview"),
    path("events", RiskEventListView.as_view(), name="risk-event-list"),
    path("events/<int:event_id>/review", RiskEventReviewView.as_view(), name="risk-event-review"),
    path("reports/company", CompanyRiskReportCreateView.as_view(), name="risk-report-company-create"),
    path("reports/<int:report_id>/export", RiskReportExportView.as_view(), name="risk-report-export"),
    path("reports/time-range", TimeRangeRiskReportCreateView.as_view(), name="risk-report-time-range-create"),
    path("sentiment/analyze", SentimentAnalyzeView.as_view(), name="risk-sentiment-analyze"),
    path(
        "documents/extract-batch",
        RiskDocumentBatchExtractView.as_view(),
        name="risk-document-batch-extract",
    ),
    path(
        "documents/extract-batch/retry",
        RiskDocumentBatchExtractRetryView.as_view(),
        name="risk-document-batch-extract-retry",
    ),
    path(
        "documents/<int:document_id>/extract",
        RiskDocumentExtractView.as_view(),
        name="risk-document-extract",
    ),
    path(
        "documents/<int:document_id>/extract/retry",
        RiskDocumentExtractRetryView.as_view(),
        name="risk-document-extract-retry",
    ),
]
