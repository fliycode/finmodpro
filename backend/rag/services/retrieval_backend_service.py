from django.conf import settings

from rag.services.lightrag_retrieval_service import retrieve_from_lightrag
from rag.services.llamaindex_store_service import query_llamaindex_store
from rag.services.vector_store_service import query_store


def _normalize_backend(name, *, default):
    normalized = str(name or default).strip().lower()
    if normalized in {"llamaindex", "native", "lightrag"}:
        return normalized
    return default


def get_rag_retrieval_backend():
    return _normalize_backend(
        getattr(settings, "RAG_RETRIEVAL_BACKEND", "native"),
        default="native",
    )


def get_chat_retrieval_backend():
    return _normalize_backend(
        getattr(settings, "CHAT_RETRIEVAL_BACKEND", "lightrag"),
        default="lightrag",
    )


def retrieve_rag_context(*, query, filters=None, top_k=5, query_variants=None):
    backend = get_rag_retrieval_backend()
    if backend == "llamaindex":
        return query_llamaindex_store(
            query=query,
            filters=filters,
            top_k=top_k,
            query_variants=query_variants,
        )
    if backend == "lightrag":
        return retrieve_from_lightrag(query=query, top_k=top_k)
    return query_store(
        query=query,
        filters=filters,
        top_k=top_k,
        query_variants=query_variants,
    )


def retrieve_chat_context(*, query, filters=None, top_k=5, query_variants=None):
    backend = get_chat_retrieval_backend()
    if backend == "llamaindex":
        return query_llamaindex_store(
            query=query,
            filters=filters,
            top_k=top_k,
            query_variants=query_variants,
        )
    if backend == "native":
        return query_store(
            query=query,
            filters=filters,
            top_k=top_k,
            query_variants=query_variants,
        )
    return retrieve_from_lightrag(query=query, top_k=top_k)
