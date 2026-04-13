from django.urls import path

from knowledgebase.controllers import (
    dataset_detail_view,
    dataset_list_create_view,
    document_batch_delete_view,
    document_batch_ingest_view,
    document_chunks_view,
    document_detail_view,
    document_ingest_view,
    document_list_create_view,
    document_versions_view,
)


urlpatterns = [
    path("datasets", dataset_list_create_view, name="knowledgebase-dataset-list-create"),
    path(
        "datasets/<int:dataset_id>",
        dataset_detail_view,
        name="knowledgebase-dataset-detail",
    ),
    path("documents", document_list_create_view, name="knowledgebase-document-list-create"),
    path(
        "documents/batch/ingest",
        document_batch_ingest_view,
        name="knowledgebase-document-batch-ingest",
    ),
    path(
        "documents/batch/delete",
        document_batch_delete_view,
        name="knowledgebase-document-batch-delete",
    ),
    path(
        "documents/<int:document_id>",
        document_detail_view,
        name="knowledgebase-document-detail",
    ),
    path(
        "documents/<int:document_id>/chunks",
        document_chunks_view,
        name="knowledgebase-document-chunks",
    ),
    path(
        "documents/<int:document_id>/versions",
        document_versions_view,
        name="knowledgebase-document-versions",
    ),
    path(
        "documents/<int:document_id>/ingest",
        document_ingest_view,
        name="knowledgebase-document-ingest",
    ),
]
