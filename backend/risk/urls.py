from django.urls import path

from risk.controllers import (
    RiskDocumentBatchExtractView,
    RiskDocumentExtractView,
    RiskEventListView,
    RiskEventReviewView,
)


urlpatterns = [
    path("events", RiskEventListView.as_view(), name="risk-event-list"),
    path("events/<int:event_id>/review", RiskEventReviewView.as_view(), name="risk-event-review"),
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
