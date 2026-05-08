import logging

from django.conf import settings

from common.exceptions import ServiceConfigurationError, UpstreamServiceError
from llm.services.lightrag_proxy_service import send_lightrag_request

logger = logging.getLogger(__name__)


def _normalize_reference(ref, index):
    chunk_content = ref.get("chunk_content") or ref.get("content") or ""
    return {
        "document_id": ref.get("doc_id") or ref.get("document_id") or "",
        "chunk_id": ref.get("chunk_id") or "",
        "section_chunk_id": None,
        "document_title": ref.get("title") or ref.get("document_title") or "",
        "doc_type": ref.get("doc_type") or "",
        "source_date": ref.get("source_date") or None,
        "page_label": ref.get("page_label") or f"chunk-{index + 1}",
        "snippet": chunk_content,
        "metadata": ref.get("metadata") or {},
        "section_context_summary": None,
        "score": 1.0 / (index + 1),
        "vector_score": 0.0,
        "keyword_score": 0.0,
        "matched_queries": [],
        "source": "lightrag",
    }


def retrieve_from_lightrag(*, query, mode=None, top_k=None):
    if not getattr(settings, "LIGHTRAG_CHAT_RETRIEVAL_ENABLED", False):
        return []

    resolved_mode = mode or getattr(settings, "LIGHTRAG_CHAT_MODE", "mix")
    resolved_top_k = top_k or getattr(settings, "LIGHTRAG_CHAT_TOP_K", 5)

    payload = {
        "query": query,
        "mode": resolved_mode,
        "chunk_top_k": resolved_top_k,
        "context_only": True,
        "include_references": True,
        "include_chunk_content": True,
    }

    try:
        result = send_lightrag_request(
            method="POST",
            upstream_path="query",
            json_payload=payload,
            enforce_allow_list=True,
        )
    except (ServiceConfigurationError, UpstreamServiceError, ValueError) as exc:
        logger.warning("lightrag retrieval failed, skipping", extra={"error": str(exc), "query": query})
        return []

    references = result.get("references") or []
    return [_normalize_reference(ref, idx) for idx, ref in enumerate(references)]
