from django.urls import path

from risk.controllers import RiskDocumentBatchExtractView, RiskDocumentExtractView, RiskEventListView


urlpatterns = [
    path("events", RiskEventListView.as_view(), name="risk-event-list"),
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
