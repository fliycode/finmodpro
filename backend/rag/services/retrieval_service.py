from rag.services.rerank_service import rerank_results
from rag.services.vector_store_service import query_store


def _normalize_top_k(top_k):
    try:
        normalized = int(top_k)
    except (TypeError, ValueError) as exc:
        raise ValueError("top_k 必须是正整数。") from exc

    if normalized <= 0:
        raise ValueError("top_k 必须是正整数。")
    return normalized


def serialize_citation(item):
    citation = {
        "document_title": item.get("document_title"),
        "doc_type": item.get("doc_type"),
        "source_date": item.get("source_date"),
        "page_label": item.get("page_label"),
        "snippet": item.get("snippet"),
    }
    if "score" in item:
        citation["score"] = item["score"]
    if "rerank_score" in item:
        citation["rerank_score"] = item["rerank_score"]
    return citation


def build_retrieval_response(*, query, results):
    citations = [serialize_citation(item) for item in results]
    return {
        "query": query,
        "question": query,
        "citations": citations,
        "results": citations,
    }


def retrieve(*, query, filters=None, top_k=5):
    results = query_store(
        query=query,
        filters=filters,
        top_k=_normalize_top_k(top_k),
    )
    reranked = rerank_results(results)
    for item in reranked:
        item["rerank_score"] = item["score"]
    return reranked
