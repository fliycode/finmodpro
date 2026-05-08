import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date

from django.conf import settings
from django.db import DatabaseError, connection

from knowledgebase.models import DocumentChunk
from knowledgebase.services.vector_service import VectorService
from rag.services.embedding_service import build_embedding, tokenize


logger = logging.getLogger(__name__)

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
        searchable_text = chunk.search_text or chunk.content
        document_vectors.append(
            {
                "document_id": document.id,
                "chunk_id": chunk.id,
                "content": chunk.content,
                "metadata": chunk.metadata,
                "embedding": build_embedding(searchable_text),
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
        "matched_queries": [],
    }


def _keyword_match_score(query, chunk):
    query_tokens = tokenize(query)
    if not query_tokens:
        return 0.0

    searchable_text = (chunk.search_text or chunk.content or "").lower()
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
    title = str((chunk.metadata or {}).get("document_title") or chunk.document.title or "").lower()
    if phrase and phrase in title:
        score += 0.5
    return score


def _fallback_keyword_search(query, filters=None, limit=5):
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


def _mysql_full_text_search(query, filters=None, limit=5):
    if not getattr(settings, "RAG_MYSQL_FULLTEXT_ENABLED", False):
        return []
    if connection.vendor != "mysql":
        return []

    filters = filters or {}
    chunk_table = DocumentChunk._meta.db_table
    document_table = DocumentChunk._meta.get_field("document").related_model._meta.db_table
    where_clauses = [
        "kc.search_text <> ''",
        "MATCH(kc.search_text) AGAINST (%s IN NATURAL LANGUAGE MODE)",
    ]
    params = [query, query]

    document_id = filters.get("document_id")
    if document_id not in (None, ""):
        where_clauses.append("kc.document_id = %s")
        params.append(int(document_id))

    doc_type = filters.get("doc_type")
    if doc_type:
        where_clauses.append("d.doc_type = %s")
        params.append(doc_type)

    source_date_from = filters.get("source_date_from")
    if source_date_from:
        where_clauses.append("d.source_date >= %s")
        params.append(source_date_from)

    source_date_to = filters.get("source_date_to")
    if source_date_to:
        where_clauses.append("d.source_date <= %s")
        params.append(source_date_to)

    params.append(int(limit))

    sql = f"""
        SELECT
            kc.id,
            MATCH(kc.search_text) AGAINST (%s IN NATURAL LANGUAGE MODE) AS lexical_score
        FROM {chunk_table} kc
        INNER JOIN {document_table} d ON d.id = kc.document_id
        WHERE {' AND '.join(where_clauses)}
        ORDER BY lexical_score DESC, kc.id DESC
        LIMIT %s
    """

    try:
        with connection.cursor() as cursor:
            cursor.execute(sql, params)
            rows = cursor.fetchall()
    except DatabaseError:
        logger.exception("mysql full-text retrieval failed; falling back to token keyword search")
        return []

    if not rows:
        return []

    score_by_chunk_id = {int(chunk_id): float(score or 0.0) for chunk_id, score in rows}
    chunk_ids = list(score_by_chunk_id.keys())
    chunks_by_id = {
        chunk.id: chunk
        for chunk in DocumentChunk.objects.select_related("document").filter(id__in=chunk_ids)
    }
    results = []
    for chunk_id in chunk_ids:
        chunk = chunks_by_id.get(chunk_id)
        if chunk is None:
            continue
        lexical_score = score_by_chunk_id[chunk_id]
        results.append(_serialize_chunk_result(chunk, lexical_score, keyword_score=lexical_score))
    return results


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


def _normalize_queries(query, query_variants=None):
    seen = set()
    normalized = []
    for candidate in [query, *(query_variants or [])]:
        value = str(candidate or "").strip()
        if not value or value in seen:
            continue
        seen.add(value)
        normalized.append(value)
    return normalized or [str(query or "").strip()]


def _candidate_limit(top_k):
    normalized_top_k = max(int(top_k), 1)
    multiplier = max(int(getattr(settings, "RAG_RETRIEVAL_CANDIDATE_MULTIPLIER", 1) or 1), 1)
    floor = max(int(getattr(settings, "RAG_RETRIEVAL_CANDIDATE_FLOOR", 1) or 1), 1)
    return max(normalized_top_k * multiplier, floor)


def _result_key(result):
    chunk_id = result.get("chunk_id")
    if chunk_id is not None:
        return result["document_id"], f"chunk:{chunk_id}"
    return result["document_id"], f"section:{result.get('section_chunk_id')}"


def _merge_ranked_results(ranked_lists):
    merged = {}
    rrf_k = max(int(getattr(settings, "RAG_RRF_K", 60) or 60), 1)

    for source_name, source_query, results in ranked_lists:
        for rank, result in enumerate(results, start=1):
            key = _result_key(result)
            existing = merged.get(key)
            if existing is None:
                existing = {**result, "score": 0.0, "matched_queries": []}
                merged[key] = existing

            existing["score"] += 1.0 / (rrf_k + rank)
            existing["fusion_score"] = existing["score"]
            existing["vector_score"] = max(
                float(existing.get("vector_score") or 0.0),
                float(result.get("vector_score") or 0.0),
            )
            existing["keyword_score"] = max(
                float(existing.get("keyword_score") or 0.0),
                float(result.get("keyword_score") or 0.0),
            )
            if source_query not in existing["matched_queries"]:
                existing["matched_queries"].append(source_query)
            if source_name == "vector":
                existing["vector_source"] = "milvus"
            else:
                existing.setdefault("keyword_sources", [])
                if source_name not in existing["keyword_sources"]:
                    existing["keyword_sources"].append(source_name)

    merged_results = list(merged.values())
    merged_results.sort(
        key=lambda item: (
            item["score"],
            item.get("keyword_score", 0.0),
            item.get("vector_score", 0.0),
            item.get("chunk_id") or item.get("section_chunk_id") or 0,
        ),
        reverse=True,
    )
    return merged_results


def _search_single_query(query_text, filters, candidate_limit):
    ranked_lists = []

    vector_results = VectorService().search(
        query=query_text,
        filters=filters,
        top_k=candidate_limit,
    )
    vector_results = _expand_section_vector_results(query_text, vector_results)
    if vector_results:
        ranked_lists.append(("vector", query_text, vector_results))

    mysql_fulltext_results = _mysql_full_text_search(
        query_text,
        filters=filters,
        limit=candidate_limit,
    )
    if mysql_fulltext_results:
        ranked_lists.append(("mysql_fulltext", query_text, mysql_fulltext_results))

    fallback_keyword_results = _fallback_keyword_search(
        query_text,
        filters=filters,
        limit=candidate_limit,
    )
    if fallback_keyword_results:
        ranked_lists.append(("token_keyword", query_text, fallback_keyword_results))

    return ranked_lists


def query_store(query, filters=None, top_k=5, query_variants=None):
    candidate_limit = _candidate_limit(top_k)
    queries = _normalize_queries(query, query_variants)
    ranked_lists = []

    if len(queries) == 1:
        ranked_lists = _search_single_query(queries[0], filters, candidate_limit)
    else:
        max_workers = min(len(queries), 5)
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(_search_single_query, q, filters, candidate_limit): q
                for q in queries
            }
            for future in as_completed(futures):
                ranked_lists.extend(future.result())

    return _merge_ranked_results(ranked_lists)[: int(top_k)]
