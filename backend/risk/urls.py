from django.urls import path

from risk.controllers import RiskDocumentBatchExtractView, RiskDocumentExtractView


urlpatterns = [
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
