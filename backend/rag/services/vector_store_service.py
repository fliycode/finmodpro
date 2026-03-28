from datetime import date

from knowledgebase.models import DocumentChunk
from rag.services.embedding_service import build_embedding, cosine_similarity


_VECTOR_STORE = {}


def clear_store():
    _VECTOR_STORE.clear()
    try:
        from knowledgebase.services.vector_service import VectorService

        VectorService().clear()
    except Exception:
        return


def _normalize_source_date(raw_value):
    if not raw_value:
        return None
    if isinstance(raw_value, date):
        return raw_value
    return date.fromisoformat(raw_value)


def _matches_filters(metadata, filters):
    if not filters:
        return True

    document_id = filters.get("document_id")
    if document_id is not None and metadata.get("document_id") != int(document_id):
        return False

    doc_type = filters.get("doc_type")
    if doc_type and metadata.get("doc_type") != doc_type:
        return False

    source_date = _normalize_source_date(metadata.get("source_date"))
    source_date_from = filters.get("source_date_from")
    if source_date_from and (
        source_date is None or source_date < _normalize_source_date(source_date_from)
    ):
        return False

    source_date_to = filters.get("source_date_to")
    if source_date_to and (
        source_date is None or source_date > _normalize_source_date(source_date_to)
    ):
        return False

    return True


def index_document(document):
    document_vectors = []
    for chunk in DocumentChunk.objects.filter(document=document).order_by("chunk_index"):
        document_vectors.append(
            {
                "document_id": document.id,
                "chunk_id": chunk.id,
                "content": chunk.content,
                "metadata": chunk.metadata,
                "embedding": build_embedding(chunk.content),
            }
        )
    _VECTOR_STORE[document.id] = document_vectors


def query_store(query, filters=None, top_k=5):
    query_embedding = build_embedding(query)
    scored = []
    for document_vectors in _VECTOR_STORE.values():
        for item in document_vectors:
            if not _matches_filters(item["metadata"], filters or {}):
                continue
            metadata = item["metadata"]
            scored.append(
                {
                    "document_id": item["document_id"],
                    "chunk_id": item["chunk_id"],
                    "document_title": metadata.get("document_title"),
                    "doc_type": metadata.get("doc_type"),
                    "source_date": metadata.get("source_date"),
                    "page_label": metadata.get(
                        "page_label",
                        f"chunk-{int(metadata.get('chunk_index', 0)) + 1}",
                    ),
                    "snippet": item["content"],
                    "metadata": metadata,
                    "score": cosine_similarity(query_embedding, item["embedding"]),
                }
            )

    scored.sort(key=lambda item: item["score"], reverse=True)
    return scored[: int(top_k)]
