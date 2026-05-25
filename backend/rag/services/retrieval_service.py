"""
检索服务 —— RAG 检索的顶层编排服务。
类比 SpringBoot: 相当于 @Service 中的核心业务流程编排，
协调检索、重排序、结果序列化等子步骤，为 Controller 提供统一的检索接口。

主要功能:
- retrieve: 执行完整的检索 + 重排序流水线
- build_retrieval_response: 将检索结果序列化为 API 响应格式
- serialize_citation: 将单条检索结果序列化为引文格式
"""

from common.observability import trace_span
from rag.services.retrieval_backend_service import retrieve_rag_context
from rag.services.rerank_service import rerank_results


def _normalize_top_k(top_k):
    """
    规范化 top_k 参数，确保其为正整数。

    参数:
        top_k: 用户传入的 top_k 值。

    返回:
        int: 规范化后的正整数 top_k。

    抛出:
        ValueError: 当 top_k 不是正整数时抛出。
    """
    try:
        normalized = int(top_k)
    except (TypeError, ValueError) as exc:
        raise ValueError("top_k 必须是正整数。") from exc

    if normalized <= 0:
        raise ValueError("top_k 必须是正整数。")
    return normalized


def serialize_citation(item):
    """
    将单条检索结果序列化为引文格式，供前端展示使用。

    参数:
        item (dict): 单条检索结果，包含 document_title, doc_type, snippet 等字段。

    返回:
        dict: 序列化后的引文字典，包含 document_title, doc_type, source_date,
              page_label, snippet, score, rerank_score 等字段。
    """
    citation = {
        "document_title": item.get("document_title"),
        "doc_type": item.get("doc_type"),
        "source_date": item.get("source_date"),
        "page_label": item.get("page_label"),
        "snippet": item.get("snippet"),
    }
    if item.get("window"):
        citation["window"] = item["window"]
    if "score" in item:
        citation["score"] = item["score"]
    if "rerank_score" in item:
        citation["rerank_score"] = item["rerank_score"]
    if "keyword_score" in item:
        citation["keyword_score"] = item["keyword_score"]
    if "vector_score" in item:
        citation["vector_score"] = item["vector_score"]
    return citation


def build_retrieval_response(*, query, results):
    """
    构建检索 API 的标准响应格式。

    参数:
        query (str): 原始查询文本。
        results (list[dict]): 检索结果列表。

    返回:
        dict: 包含 query, question, citations, results 字段的响应字典。
    """
    citations = [serialize_citation(item) for item in results]
    return {
        "query": query,
        "question": query,
        "citations": citations,
        "results": citations,
    }


def retrieve(*, query, filters=None, top_k=5, query_variants=None):
    """
    执行完整的 RAG 检索流水线: 检索 -> 重排序。

    类比 SpringBoot: 相当于 @Service 中的核心业务流程方法，
    该方法被 Controller 层调用，拆解为以下步骤:
    1. 参数规范化
    2. 调用检索后端获取候选结果
    3. 调用重排序服务优化排序
    4. 补全 rerank_score 字段

    参数:
        query (str): 用户查询文本。
        filters (dict, 可选): 过滤条件字典（document_id, doc_type 等）。
        top_k (int, 可选): 返回的最大结果数量，默认 5。
        query_variants (list[str] | None, 可选): 查询变体列表，用于多查询融合检索。

    返回:
        list[dict]: 经过检索和重排序后的结果列表，每项包含 document_id,
                    snippet, score, rerank_score 等字段。
    """
    normalized_top_k = _normalize_top_k(top_k)
    normalized_query_variants = [str(item).strip() for item in (query_variants or []) if str(item).strip()]
    with trace_span(
        "rag.retrieve",
        metadata={
            "top_k": normalized_top_k,
            "has_filters": bool(filters),
            "query_variant_count": len(normalized_query_variants) or 1,
        },
        input_data={"query": query},
    ) as observation:
        results = retrieve_rag_context(
            query=query,
            filters=filters,
            top_k=normalized_top_k,
            query_variants=normalized_query_variants,
        )
        reranked = rerank_results(results, query=query)
        for item in reranked:
            if "rerank_score" not in item:
                item["rerank_score"] = item.get("score", 0.0)
        observation.update(output={"result_count": len(reranked)})
        return reranked
