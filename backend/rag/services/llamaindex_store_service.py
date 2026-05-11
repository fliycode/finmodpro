import copy
import logging
import threading
import time

from django.conf import settings

from llama_index.core import StorageContext, VectorStoreIndex
from llama_index.core.schema import TextNode
from llama_index.core.vector_stores.types import (
    FilterOperator,
    MetadataFilter,
    MetadataFilters,
)
from llama_index.vector_stores.milvus import MilvusVectorStore

from knowledgebase.models import DocumentChunk
from rag.services.llamaindex_embedding_adapter import FinModProEmbeddingAdapter

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# BM25 retriever cache (thread-safe, TTL-based)
# ---------------------------------------------------------------------------

_bm25_cache_lock = threading.Lock()
_bm25_cache = {"retriever": None, "built_at": 0.0}


def invalidate_bm25_cache():
    with _bm25_cache_lock:
        _bm25_cache["retriever"] = None
        _bm25_cache["built_at"] = 0.0


def _build_milvus_vector_store():
    kwargs = {
        "uri": settings.MILVUS_URI,
        "collection_name": settings.MILVUS_COLLECTION_NAME,
        "dim": settings.KB_EMBEDDING_DIMENSION,
        "embedding_field": "vector",
        "text_key": "content",
        "similarity_metric": "COSINE",
        "overwrite": False,
    }
    token = getattr(settings, "MILVUS_TOKEN", "")
    if token:
        kwargs["token"] = token
    return MilvusVectorStore(**kwargs)


def _build_embed_model():
    return FinModProEmbeddingAdapter()


def _build_index():
    vector_store = _build_milvus_vector_store()
    storage_context = StorageContext.from_defaults(vector_store=vector_store)
    return VectorStoreIndex(
        nodes=[],
        storage_context=storage_context,
        embed_model=_build_embed_model(),
    )


def _build_filter_expression(filters):
    filters = filters or {}
    clauses = []

    document_id = filters.get("document_id")
    if document_id not in (None, ""):
        clauses.append(f"document_id == {int(document_id)}")

    doc_type = filters.get("doc_type")
    if doc_type:
        clauses.append(f'doc_type == "{doc_type}"')

    source_date_from = filters.get("source_date_from")
    if source_date_from:
        clauses.append(f'source_date >= "{source_date_from}"')

    source_date_to = filters.get("source_date_to")
    if source_date_to:
        clauses.append(f'source_date <= "{source_date_to}"')

    return " and ".join(clauses) if clauses else None


def _build_node_id(chunk_id):
    return f"chunk:{int(chunk_id)}"


def _build_chunk_node(chunk):
    metadata = chunk.metadata or {}
    document = chunk.document
    return TextNode(
        id_=_build_node_id(chunk.id),
        text=chunk.search_text or chunk.content,
        metadata={
            "document_id": document.id,
            "chunk_id": chunk.id,
            "document_title": metadata.get("document_title") or document.title,
            "doc_type": metadata.get("doc_type") or document.doc_type,
            "source_date": metadata.get("source_date")
            or (document.source_date.isoformat() if document.source_date else None),
            "page_label": metadata.get(
                "page_label", f"chunk-{chunk.chunk_index + 1}"
            ),
            "chunk_index": chunk.chunk_index,
            "window": metadata.get("window", ""),
        },
    )


def _serialize_chunk_result(chunk, score):
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
        "window": metadata.get("window", ""),
        "metadata": metadata,
        "section_context_summary": None,
        "score": score,
        "vector_score": score,
        "keyword_score": 0.0,
        "matched_queries": [],
    }


def sync_document(document):
    from knowledgebase.services.vector_service import VectorService

    VectorService().index(document)
    invalidate_bm25_cache()


def delete_document(*, document_id, chunk_ids=None):
    resolved_chunk_ids = [int(chunk_id) for chunk_id in (chunk_ids or [])]
    if not resolved_chunk_ids:
        resolved_chunk_ids = list(
            DocumentChunk.objects.filter(document_id=document_id).values_list(
                "id", flat=True
            )
        )
    if not resolved_chunk_ids:
        return

    try:
        vector_store = _build_milvus_vector_store()
        for chunk_id in resolved_chunk_ids:
            vector_store.delete(str(chunk_id))
    except Exception:
        logger.exception("failed to delete llamaindex nodes for document %s", document_id)
    invalidate_bm25_cache()


def clear_store():
    try:
        vector_store = _build_milvus_vector_store()
        vector_store.clear()
    except Exception:
        logger.exception("failed to clear llamaindex milvus store")
    invalidate_bm25_cache()


# ---------------------------------------------------------------------------
# BM25 retrieval
# ---------------------------------------------------------------------------


def _build_bm25_retriever_from_db():
    from llama_index.retrievers.bm25 import BM25Retriever

    chunks = list(
        DocumentChunk.objects.select_related("document")
        .exclude(search_text="")
        .iterator(chunk_size=1000)
    )
    if not chunks:
        return None

    nodes = []
    for chunk in chunks:
        node = _build_chunk_node(chunk)
        nodes.append(node)

    language = getattr(settings, "RAG_BM25_LANGUAGE", "zh")
    return BM25Retriever(
        nodes=nodes,
        similarity_top_k=20,
        language=language,
        verbose=False,
    )


def _get_or_build_bm25_retriever():
    cache_ttl = max(int(getattr(settings, "RAG_BM25_CACHE_TTL", 600) or 600), 60)
    now = time.monotonic()

    with _bm25_cache_lock:
        cached = _bm25_cache
        if cached["retriever"] is not None and (now - cached["built_at"]) < cache_ttl:
            return cached["retriever"]

    retriever = _build_bm25_retriever_from_db()
    if retriever is None:
        return None

    with _bm25_cache_lock:
        _bm25_cache["retriever"] = retriever
        _bm25_cache["built_at"] = time.monotonic()

    return retriever


def _build_bm25_metadata_filters(filters):
    if not filters:
        return None

    metadata_filters = []

    document_id = filters.get("document_id")
    if document_id not in (None, ""):
        metadata_filters.append(
            MetadataFilter(key="document_id", value=int(document_id), operator=FilterOperator.EQ)
        )

    doc_type = filters.get("doc_type")
    if doc_type:
        metadata_filters.append(
            MetadataFilter(key="doc_type", value=doc_type, operator=FilterOperator.EQ)
        )

    source_date_from = filters.get("source_date_from")
    if source_date_from:
        metadata_filters.append(
            MetadataFilter(key="source_date", value=source_date_from, operator=FilterOperator.GTE)
        )

    source_date_to = filters.get("source_date_to")
    if source_date_to:
        metadata_filters.append(
            MetadataFilter(key="source_date", value=source_date_to, operator=FilterOperator.LTE)
        )

    if not metadata_filters:
        return None
    return MetadataFilters(filters=metadata_filters)


def _serialize_bm25_results(nodes):
    if not nodes:
        return []

    score_by_chunk_id = {}
    for node_with_score in nodes:
        metadata = node_with_score.node.metadata or {}
        chunk_id = metadata.get("chunk_id")
        if chunk_id in (None, ""):
            continue
        score_by_chunk_id[int(chunk_id)] = max(
            score_by_chunk_id.get(int(chunk_id), 0.0),
            float(node_with_score.score or 0.0),
        )

    if not score_by_chunk_id:
        return []

    chunks_by_id = {
        chunk.id: chunk
        for chunk in DocumentChunk.objects.select_related("document").filter(
            id__in=score_by_chunk_id.keys()
        )
    }
    results = []
    for chunk_id, score in score_by_chunk_id.items():
        chunk = chunks_by_id.get(chunk_id)
        if chunk is None:
            continue
        metadata = chunk.metadata or {}
        results.append({
            "document_id": chunk.document_id,
            "chunk_id": chunk.id,
            "section_chunk_id": chunk.section_chunk_id,
            "document_title": metadata.get("document_title") or chunk.document.title,
            "doc_type": metadata.get("doc_type") or chunk.document.doc_type,
            "source_date": metadata.get("source_date")
            or (chunk.document.source_date.isoformat() if chunk.document.source_date else None),
            "page_label": metadata.get("page_label", f"chunk-{chunk.chunk_index + 1}"),
            "snippet": chunk.content,
            "window": metadata.get("window", ""),
            "metadata": metadata,
            "section_context_summary": None,
            "score": score,
            "vector_score": 0.0,
            "keyword_score": score,
            "matched_queries": [],
        })
    return results


def _bm25_search(query, filters=None, limit=5):
    if not getattr(settings, "RAG_BM25_ENABLED", False):
        return []

    retriever = _get_or_build_bm25_retriever()
    if retriever is None:
        return []

    retriever_copy = copy.copy(retriever)
    retriever_copy.similarity_top_k = max(int(limit), 1)

    metadata_filters = _build_bm25_metadata_filters(filters)
    if metadata_filters:
        retriever_copy.filters = metadata_filters

    nodes = retriever_copy.retrieve(query)
    return _serialize_bm25_results(nodes)


def search(*, query, filters=None, top_k=5):
    index = _build_index()
    filter_expr = _build_filter_expression(filters)

    retriever_kwargs = {"similarity_top_k": max(int(top_k), 1)}
    if filter_expr:
        retriever_kwargs["vector_store_kwargs"] = {"filter": filter_expr}

    retriever = index.as_retriever(**retriever_kwargs)
    retrieved_nodes = retriever.retrieve(query)

    if not retrieved_nodes:
        return []

    score_by_chunk_id = {}
    for result in retrieved_nodes:
        metadata = result.node.metadata or {}
        chunk_id = metadata.get("chunk_id")
        if chunk_id in (None, ""):
            continue
        score_by_chunk_id[int(chunk_id)] = max(
            score_by_chunk_id.get(int(chunk_id), 0.0),
            float(result.score or 0.0),
        )

    if not score_by_chunk_id:
        return []

    chunks_by_id = {
        chunk.id: chunk
        for chunk in DocumentChunk.objects.select_related("document").filter(
            id__in=score_by_chunk_id.keys()
        )
    }
    results = []
    for chunk_id, score in score_by_chunk_id.items():
        chunk = chunks_by_id.get(chunk_id)
        if chunk is None:
            continue
        row = _serialize_chunk_result(chunk, score)
        results.append(row)

    results.sort(
        key=lambda item: (item.get("score", 0.0), item.get("chunk_id") or 0),
        reverse=True,
    )
    return results[: int(top_k)]


def _candidate_limit(top_k):
    normalized_top_k = max(int(top_k), 1)
    multiplier = max(
        int(getattr(settings, "RAG_RETRIEVAL_CANDIDATE_MULTIPLIER", 1) or 1), 1
    )
    floor = max(int(getattr(settings, "RAG_RETRIEVAL_CANDIDATE_FLOOR", 1) or 1), 1)
    return max(normalized_top_k * multiplier, floor)


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


def _merge_ranked_results(ranked_lists):
    merged = {}
    rrf_k = max(int(getattr(settings, "RAG_RRF_K", 60) or 60), 1)

    for source_name, source_query, results in ranked_lists:
        for rank, result in enumerate(results, start=1):
            key = (result.get("document_id"), result.get("chunk_id"))
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

    merged_results = list(merged.values())
    merged_results.sort(
        key=lambda item: (
            item["score"],
            item.get("keyword_score", 0.0),
            item.get("vector_score", 0.0),
            item.get("chunk_id") or 0,
        ),
        reverse=True,
    )
    return merged_results


def _mysql_full_text_search(query, filters=None, limit=5):
    if not getattr(settings, "RAG_MYSQL_FULLTEXT_ENABLED", False):
        return []
    from django.db import connection

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
    except Exception:
        logger.exception("mysql full-text retrieval failed")
        return []

    if not rows:
        return []

    from datetime import date as date_type

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
        metadata = chunk.metadata or {}
        results.append({
            "document_id": chunk.document_id,
            "chunk_id": chunk.id,
            "section_chunk_id": chunk.section_chunk_id,
            "document_title": metadata.get("document_title") or chunk.document.title,
            "doc_type": metadata.get("doc_type") or chunk.document.doc_type,
            "source_date": metadata.get("source_date")
            or (chunk.document.source_date.isoformat() if chunk.document.source_date else None),
            "page_label": metadata.get("page_label", f"chunk-{chunk.chunk_index + 1}"),
            "snippet": chunk.content,
            "window": metadata.get("window", ""),
            "metadata": metadata,
            "section_context_summary": None,
            "score": lexical_score,
            "vector_score": 0.0,
            "keyword_score": lexical_score,
            "matched_queries": [],
        })
    return results


def _keyword_match_score(query, chunk):
    import re
    import math
    from collections import Counter

    token_pattern = re.compile(r"[\w一-鿿]+", re.UNICODE)
    query_tokens = token_pattern.findall((query or "").lower())
    if not query_tokens:
        return 0.0

    searchable_text = (chunk.search_text or chunk.content or "").lower()
    content_tokens = token_pattern.findall(searchable_text)
    if not content_tokens:
        return 0.0

    unique_query_tokens = set(query_tokens)
    content_token_set = set(content_tokens)
    matched_token_count = sum(1 for token in unique_query_tokens if token in content_token_set)
    if matched_token_count == 0:
        return 0.0

    score = matched_token_count / max(len(unique_query_tokens), 1)
    phrase = " ".join(query_tokens)
    if phrase and phrase in searchable_text:
        score += 0.5
    title = str((chunk.metadata or {}).get("document_title") or chunk.document.title or "").lower()
    if phrase and phrase in title:
        score += 0.5
    return score


def _fallback_keyword_search(query, filters=None, limit=5):
    import re

    token_pattern = re.compile(r"[\w一-鿿]+", re.UNICODE)
    query_tokens = token_pattern.findall((query or "").lower())
    if not query_tokens:
        return []
    query_phrase = " ".join(query_tokens)

    def _matches_filters(metadata, filters):
        if not filters:
            return True
        from datetime import date as date_type

        document_id = filters.get("document_id")
        if document_id is not None and metadata.get("document_id") != int(document_id):
            return False
        doc_type = filters.get("doc_type")
        if doc_type and metadata.get("doc_type") != doc_type:
            return False
        source_date = metadata.get("source_date")
        if source_date and isinstance(source_date, str):
            try:
                source_date = date_type.fromisoformat(source_date)
            except ValueError:
                source_date = None
        source_date_from = filters.get("source_date_from")
        if source_date_from:
            try:
                from_date = date_type.fromisoformat(source_date_from) if isinstance(source_date_from, str) else source_date_from
                if source_date is None or source_date < from_date:
                    return False
            except ValueError:
                pass
        source_date_to = filters.get("source_date_to")
        if source_date_to:
            try:
                to_date = date_type.fromisoformat(source_date_to) if isinstance(source_date_to, str) else source_date_to
                if source_date is None or source_date > to_date:
                    return False
            except ValueError:
                pass
        return True

    results = []
    queryset = (
        DocumentChunk.objects.select_related("document")
        .only(
            "id",
            "document_id",
            "section_chunk_id",
            "content",
            "search_text",
            "metadata",
            "chunk_index",
            "document__title",
            "document__doc_type",
            "document__source_date",
        )
    )
    for chunk in queryset.iterator(chunk_size=500):
        if not _matches_filters(chunk.metadata or {}, filters or {}):
            continue
        keyword_score = _keyword_match_score(query, chunk)
        if keyword_score <= 0:
            continue
        metadata = chunk.metadata or {}
        results.append({
            "document_id": chunk.document_id,
            "chunk_id": chunk.id,
            "section_chunk_id": chunk.section_chunk_id,
            "document_title": metadata.get("document_title") or chunk.document.title,
            "doc_type": metadata.get("doc_type") or chunk.document.doc_type,
            "source_date": metadata.get("source_date")
            or (chunk.document.source_date.isoformat() if chunk.document.source_date else None),
            "page_label": metadata.get("page_label", f"chunk-{chunk.chunk_index + 1}"),
            "snippet": chunk.content,
            "window": metadata.get("window", ""),
            "metadata": metadata,
            "section_context_summary": None,
            "score": keyword_score,
            "vector_score": 0.0,
            "keyword_score": keyword_score,
            "matched_queries": [],
        })
    results.sort(key=lambda item: item["score"], reverse=True)
    return results[: int(limit)]


def query_llamaindex_store(
    query,
    filters=None,
    top_k=5,
    query_variants=None,
    allow_keyword_fallback=True,
):
    candidate_limit = _candidate_limit(top_k)
    queries = _normalize_queries(query, query_variants)
    ranked_lists = []

    for query_text in queries:
        vector_results = search(
            query=query_text,
            filters=filters,
            top_k=candidate_limit,
        )
        if vector_results:
            ranked_lists.append(("llamaindex_vector", query_text, vector_results))

        bm25_results = _bm25_search(
            query_text,
            filters=filters,
            limit=candidate_limit,
        )
        if bm25_results:
            ranked_lists.append(("bm25", query_text, bm25_results))

        mysql_fulltext_results = _mysql_full_text_search(
            query_text,
            filters=filters,
            limit=candidate_limit,
        )
        if mysql_fulltext_results:
            ranked_lists.append(("mysql_fulltext", query_text, mysql_fulltext_results))

        should_run_keyword_fallback = allow_keyword_fallback and not (
            vector_results or bm25_results or mysql_fulltext_results
        )
        if should_run_keyword_fallback:
            fallback_keyword_results = _fallback_keyword_search(
                query_text,
                filters=filters,
                limit=candidate_limit,
            )
            if fallback_keyword_results:
                ranked_lists.append(("token_keyword", query_text, fallback_keyword_results))

    return _merge_ranked_results(ranked_lists)[: int(top_k)]
