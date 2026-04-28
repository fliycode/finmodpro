from datetime import date

from knowledgebase.models import DocumentChunk
from knowledgebase.services.vector_service import VectorService
from rag.services.embedding_service import build_embedding, cosine_similarity, tokenize


_VECTOR_STORE = {}


def clear_store():
    _VECTOR_STORE.clear()
    try:
        VectorService().clear()
    except Exception:
        return


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


def _serialize_chunk_result(chunk, score, *, keyword_score=0.0):
    metadata = chunk.metadata or {}
    return {
        "document_id": chunk.document_id,
        "chunk_id": chunk.id,
        "section_chunk_id": chunk.section_chunk_id,
        "document_title": metadata.get("document_title") or chunk.document.title,
        "doc_type": metadata.get("doc_type") or chunk.document.doc_type,
        "source_date": metadata.get("source_date")
        or (chunk.document.source_date.isoformat() if chunk.document.source_date else None),
        "page_label": metadata.get("page_label", f"chunk-{chunk.chunk_index + 1}"),
        "snippet": chunk.content,
        "metadata": metadata,
        "section_context_summary": None,
        "score": score,
        "vector_score": 0.0,
        "keyword_score": keyword_score,
    }


def _keyword_match_score(query, chunk):
    query_tokens = tokenize(query)
    if not query_tokens:
        return 0.0

    metadata = chunk.metadata or {}
    title = (metadata.get("document_title") or chunk.document.title or "").lower()
    content = (chunk.content or "").lower()
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
    results = []
    queryset = DocumentChunk.objects.select_related("document").order_by("id")
    for chunk in queryset:
        if not _matches_filters(chunk.metadata or {}, filters or {}):
            continue
        keyword_score = _keyword_match_score(query, chunk)
        if keyword_score <= 0:
            continue
        results.append(_serialize_chunk_result(chunk, keyword_score, keyword_score=keyword_score))
    results.sort(key=lambda item: item["score"], reverse=True)
    return results[: int(limit)]


def _expand_section_vector_results(query, vector_results):
    expanded_results = []
    for result in vector_results:
        section_chunk_id = result.get("section_chunk_id")
        if not section_chunk_id:
            expanded_results.append(result)
            continue

        child_chunks = list(
            DocumentChunk.objects.select_related("document")
            .filter(section_chunk_id=section_chunk_id)
            .order_by("chunk_index")
        )
        if not child_chunks:
            continue

        ranked_children = sorted(
            child_chunks,
            key=lambda chunk: (_keyword_match_score(query, chunk), -chunk.chunk_index),
            reverse=True,
        )
        best_child = ranked_children[0]
        expanded = _serialize_chunk_result(best_child, result.get("score", 0.0))
        expanded["vector_score"] = result.get("vector_score", result.get("score", 0.0))
        expanded["score"] = result.get("score", 0.0)
        expanded["section_chunk_id"] = section_chunk_id
        expanded_results.append(expanded)
    return expanded_results


def _merge_scored_results(vector_results, keyword_results):
    merged = {}
    for result in vector_results + keyword_results:
        key = (result["document_id"], result["chunk_id"])
        existing = merged.get(key)
        if existing is None:
            merged[key] = result
            continue
        existing["vector_score"] = max(existing.get("vector_score", 0.0), result.get("vector_score", 0.0))
        existing["keyword_score"] = max(existing.get("keyword_score", 0.0), result.get("keyword_score", 0.0))
        existing["score"] = max(existing.get("score", 0.0), result.get("score", 0.0))

    merged_results = []
    for result in merged.values():
        result["score"] = (result.get("vector_score", 0.0) * 0.7) + (
            result.get("keyword_score", 0.0) * 0.3
        )
        merged_results.append(result)

    merged_results.sort(
        key=lambda item: (
            item["score"],
            item.get("keyword_score", 0.0),
            item.get("vector_score", 0.0),
            item["chunk_id"],
        ),
        reverse=True,
    )
    return merged_results


def query_store(query, filters=None, top_k=5):
    candidate_limit = max(int(top_k), 1) * 2
    vector_results = VectorService().search(query=query, filters=filters, top_k=candidate_limit)
    vector_results = _expand_section_vector_results(query, vector_results)
    keyword_results = _keyword_search(query, filters=filters, limit=candidate_limit)
    return _merge_scored_results(vector_results, keyword_results)[: int(top_k)]
