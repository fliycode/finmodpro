from rag.services.llamaindex_store_service import query_llamaindex_store


def retrieve_rag_context(*, query, filters=None, top_k=5, query_variants=None):
    return query_llamaindex_store(
        query=query,
        filters=filters,
        top_k=top_k,
        query_variants=query_variants,
        allow_keyword_fallback=True,
    )


def retrieve_chat_context(*, query, filters=None, top_k=5, query_variants=None):
    from django.conf import settings

    allow_keyword_fallback = bool(
        getattr(settings, "CHAT_RAG_KEYWORD_FALLBACK_ENABLED", False)
    )
    return query_llamaindex_store(
        query=query,
        filters=filters,
        top_k=top_k,
        query_variants=query_variants,
        allow_keyword_fallback=allow_keyword_fallback,
    )
