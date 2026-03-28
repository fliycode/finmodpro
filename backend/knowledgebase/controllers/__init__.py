from knowledgebase.controllers.document_controller import (
    document_detail_view,
    document_list_create_view,
)
from knowledgebase.controllers.ingest_controller import document_ingest_view


__all__ = [
    "document_detail_view",
    "document_ingest_view",
    "document_list_create_view",
]
