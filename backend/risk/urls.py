from django.urls import path

from risk.controllers import RiskDocumentExtractView


urlpatterns = [
    path(
        "documents/<int:document_id>/extract",
        RiskDocumentExtractView.as_view(),
        name="risk-document-extract",
    ),
]
