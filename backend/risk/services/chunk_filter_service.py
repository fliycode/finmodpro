from django.conf import settings

from common.observability import trace_span
from rag.services.llamaindex_store_service import query_llamaindex_store

RISK_QUERY_VARIANTS = [
    "金融风险事件",
    "流动性风险 信用风险",
    "合规风险 操作风险",
    "市场风险 风险预警",
]


def select_risk_relevant_chunks(*, document, all_chunks, top_k=None):
    total = len(all_chunks)
    threshold = getattr(settings, "RISK_EXTRACTION_SMALL_DOC_THRESHOLD", 10)
    min_filtered = getattr(settings, "RISK_EXTRACTION_MIN_FILTERED_CHUNKS", 3)
    effective_top_k = top_k or getattr(settings, "RISK_EXTRACTION_CHUNK_TOP_K", 20)

    if total <= threshold:
        with trace_span(
            "risk.chunk_filter",
            metadata={"total_chunks": total, "filtered_chunks": total, "skipped": True, "reason": "small_document"},
        ):
            return list(all_chunks)

    with trace_span(
        "risk.chunk_filter",
        metadata={"total_chunks": total, "top_k": effective_top_k},
    ) as observation:
        results = query_llamaindex_store(
            query=RISK_QUERY_VARIANTS[0],
            filters={"document_id": document.id},
            top_k=min(effective_top_k, total),
            query_variants=RISK_QUERY_VARIANTS[1:],
            allow_keyword_fallback=True,
        )

        retrieved_ids = {int(r["chunk_id"]) for r in results if r.get("chunk_id") is not None}
        chunk_by_id = {chunk.id: chunk for chunk in all_chunks}
        filtered = [chunk_by_id[cid] for cid in sorted(retrieved_ids) if cid in chunk_by_id]

        if len(filtered) < min_filtered:
            observation.update(output={
                "filtered_chunks": total,
                "fallback": True,
                "reason": "too_few_results",
            })
            return list(all_chunks)

        filtered.sort(key=lambda c: (c.chunk_index, c.id))
        observation.update(output={"filtered_chunks": len(filtered), "fallback": False})
        return filtered
