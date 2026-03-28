from datetime import date

from knowledgebase.models import DocumentChunk
from rag.services.embedding_service import build_embedding, cosine_similarity, tokenize


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


def _serialize_scored_item(item, score, *, vector_score=0.0, keyword_score=0.0):
    metadata = item["metadata"]
    return {
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
        "score": score,
        "vector_score": vector_score,
        "keyword_score": keyword_score,
    }


def _vector_search(query, filters=None, limit=5):
    query_embedding = build_embedding(query)
    scored = []
    for document_vectors in _VECTOR_STORE.values():
        for item in document_vectors:
            if not _matches_filters(item["metadata"], filters or {}):
                continue
            vector_score = cosine_similarity(query_embedding, item["embedding"])
            if vector_score <= 0:
                continue
            scored.append(
                _serialize_scored_item(
                    item,
                    vector_score,
                    vector_score=vector_score,
                    keyword_score=0.0,
                )
            )

    scored.sort(key=lambda item: item["score"], reverse=True)
    return scored[: int(limit)]


def _keyword_match_score(query, item):
    query_tokens = tokenize(query)
    if not query_tokens:
        return 0.0

    title = (item["metadata"].get("document_title") or "").lower()
    content = (item["content"] or "").lower()
    searchable_text = f"{title}\n{content}"
    content_tokens = tokenize(searchable_text)
    if not content_tokens:
        return 0.0

    matched_token_count = sum(1 for token in query_tokens if token in content_tokens)
    if matched_token_count == 0:
        return 0.0

    unique_query_tokens = max(len(set(query_tokens)), 1)
    score = matched_token_count / unique_query_tokens
    phrase = " ".join(query_tokens)
    if phrase and phrase in searchable_text:
        score += 0.5
    if phrase and phrase in title:
        score += 0.5
    return score


def _keyword_search(query, filters=None, limit=5):
    scored = []
    for document_vectors in _VECTOR_STORE.values():
        for item in document_vectors:
            if not _matches_filters(item["metadata"], filters or {}):
                continue
            keyword_score = _keyword_match_score(query, item)
            if keyword_score <= 0:
                continue
            scored.append(
                _serialize_scored_item(
                    item,
                    keyword_score,
                    vector_score=0.0,
                    keyword_score=keyword_score,
                )
            )

    scored.sort(key=lambda item: item["score"], reverse=True)
    return scored[: int(limit)]


def _merge_scored_results(vector_results, keyword_results):
    merged = {}
    for result in vector_results + keyword_results:
        key = (result["document_id"], result["chunk_id"])
        existing = merged.get(key)
        if existing is None:
            merged[key] = result
            continue
        existing["vector_score"] = max(existing["vector_score"], result["vector_score"])
        existing["keyword_score"] = max(existing["keyword_score"], result["keyword_score"])

    merged_results = []
    for result in merged.values():
        result["score"] = (result["vector_score"] * 0.7) + (result["keyword_score"] * 0.3)
        merged_results.append(result)

    merged_results.sort(
        key=lambda item: (
            item["score"],
            item["keyword_score"],
            item["vector_score"],
            item["chunk_id"],
        ),
        reverse=True,
    )
    return merged_results


def query_store(query, filters=None, top_k=5):
    candidate_limit = max(int(top_k), 1) * 2
    vector_results = _vector_search(query, filters=filters, limit=candidate_limit)
    keyword_results = _keyword_search(query, filters=filters, limit=candidate_limit)
    return _merge_scored_results(vector_results, keyword_results)[: int(top_k)]
