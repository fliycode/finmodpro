from django.urls import path

from knowledgebase.controllers import (
    document_detail_view,
    document_ingest_view,
    document_list_create_view,
)


urlpatterns = [
    path("documents", document_list_create_view, name="knowledgebase-document-list-create"),
    path(
        "documents/<int:document_id>",
        document_detail_view,
        name="knowledgebase-document-detail",
    ),
    path(
        "documents/<int:document_id>/ingest",
        document_ingest_view,
        name="knowledgebase-document-ingest",
    ),
]
