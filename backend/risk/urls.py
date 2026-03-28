from django.urls import path

from risk.controllers import (
    CompanyRiskReportCreateView,
    RiskDocumentBatchExtractView,
    RiskDocumentExtractView,
    RiskEventListView,
    RiskEventReviewView,
    TimeRangeRiskReportCreateView,
)


urlpatterns = [
    path("events", RiskEventListView.as_view(), name="risk-event-list"),
    path("events/<int:event_id>/review", RiskEventReviewView.as_view(), name="risk-event-review"),
    path("reports/company", CompanyRiskReportCreateView.as_view(), name="risk-report-company-create"),
    path("reports/time-range", TimeRangeRiskReportCreateView.as_view(), name="risk-report-time-range-create"),
    path(
        "documents/extract-batch",
        RiskDocumentBatchExtractView.as_view(),
        name="risk-document-batch-extract",
    ),
    path(
        "documents/<int:document_id>/extract",
        RiskDocumentExtractView.as_view(),
        name="risk-document-extract",
    ),
]
