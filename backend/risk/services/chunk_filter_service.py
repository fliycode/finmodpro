"""
切块筛选服务 —— 从文档的所有 chunk 中筛选出与风险相关的内容块。
类比 SpringBoot: 相当于 @Service 中的预处理层，
通过 RAG 检索过滤掉不相关的 chunk，减少后续 LLM 处理的 token 消耗。

逻辑:
- 小文档（chunk 数 <= 阈值）: 全员参与，不做筛选
- 大文档: 使用 RAG 检索，筛选出与预定义风险关键词匹配的 chunk
- 结果不足时: 降级为全部 chunk
"""

import logging

from django.conf import settings

from common.observability import trace_span
from rag.services.llamaindex_store_service import query_llamaindex_store

logger = logging.getLogger(__name__)

# 用于筛选风险相关内容的查询变体列表
RISK_QUERY_VARIANTS = [
    "金融风险事件",
    "流动性风险 信用风险",
    "合规风险 操作风险",
    "市场风险 风险预警",
]


def select_risk_relevant_chunks(*, document, all_chunks, top_k=None):
    """
    从文档的所有 chunk 中筛选出与风险最相关的子集。

    类比 SpringBoot: 相当于数据预处理 Pipeline 中的过滤器。

    参数:
        document (Document): 文档实例。
        all_chunks (list[DocumentChunk]): 文档的所有分块列表。
        top_k (int, 可选): 检索的最大数量，默认从配置读取。

    返回:
        list[DocumentChunk]: 筛选后的 chunk 列表，按 chunk_index 排序。
                            如果文档很小或检索失败，返回完整的 all_chunks。
    """
    total = len(all_chunks)
    threshold = getattr(settings, "RISK_EXTRACTION_SMALL_DOC_THRESHOLD", 10)
    min_filtered = getattr(settings, "RISK_EXTRACTION_MIN_FILTERED_CHUNKS", 3)
    effective_top_k = top_k or getattr(settings, "RISK_EXTRACTION_CHUNK_TOP_K", 20)

    # 小文档不做筛选
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
        try:
            results = query_llamaindex_store(
                query=RISK_QUERY_VARIANTS[0],
                filters={"document_id": document.id},
                top_k=min(effective_top_k, total),
                query_variants=RISK_QUERY_VARIANTS[1:],
                allow_keyword_fallback=True,
                provider_options={
                    "timeout_seconds": getattr(settings, "RISK_EXTRACTION_RETRIEVAL_TIMEOUT_SECONDS", 20),
                    "transport_retry_attempts": 1,
                },
            )
        except Exception:
            logger.exception(
                "Risk chunk retrieval failed; falling back to document-order chunks",
                extra={"document_id": document.id, "total_chunks": total},
            )
            observation.update(output={
                "filtered_chunks": total,
                "fallback": True,
                "reason": "retrieval_failed",
            })
            return list(all_chunks)

        retrieved_ids = {int(r["chunk_id"]) for r in results if r.get("chunk_id") is not None}
        chunk_by_id = {chunk.id: chunk for chunk in all_chunks}
        filtered = [chunk_by_id[cid] for cid in sorted(retrieved_ids) if cid in chunk_by_id]

        # 筛选结果太少时，降级为全部 chunk
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
