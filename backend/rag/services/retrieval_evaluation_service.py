import json
import math
from pathlib import Path
from time import perf_counter

from rag.services.retrieval_service import retrieve


DEFAULT_RETRIEVAL_EVAL_FIXTURE = (
    Path(__file__).resolve().parent.parent / "data" / "retrieval_smoke_cases.json"
)


def load_retrieval_cases(path=None):
    fixture_path = Path(path or DEFAULT_RETRIEVAL_EVAL_FIXTURE)
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("retrieval evaluation fixture must be a JSON array.")
    return payload


def _expected_relevance_targets(case):
    for key in ("relevant_chunk_ids", "relevant_document_titles", "relevant_page_labels"):
        raw_values = case.get(key) or []
        values = []
        for raw_value in raw_values:
            value = str(raw_value).strip()
            if value and value not in values:
                values.append(value)
        if values:
            return key, values
    return None, []


def _result_matches_target(result, target_type, target):
    if target_type == "relevant_chunk_ids":
        return str(result.get("chunk_id")) == str(target)
    if target_type == "relevant_document_titles":
        return str(result.get("document_title") or "").strip() == str(target)
    if target_type == "relevant_page_labels":
        return str(result.get("page_label") or "").strip() == str(target)
    return False


def _binary_relevance_hits(results, target_type, targets):
    return [
        1 if any(_result_matches_target(result, target_type, target) for target in targets) else 0
        for result in results
    ]


def _recall_at_k(results, target_type, targets):
    if not targets:
        return 0.0
    matched_targets = {
        target
        for target in targets
        if any(_result_matches_target(result, target_type, target) for result in results)
    }
    return len(matched_targets) / len(targets)


def _mrr(hits):
    for index, hit in enumerate(hits, start=1):
        if hit:
            return 1.0 / index
    return 0.0


def _ndcg_at_k(hits, target_count):
    if not target_count:
        return 0.0
    dcg = 0.0
    for index, hit in enumerate(hits, start=1):
        if hit:
            dcg += 1.0 / math.log2(index + 1)
    ideal_hits = [1] * min(target_count, len(hits))
    idcg = 0.0
    for index, hit in enumerate(ideal_hits, start=1):
        if hit:
            idcg += 1.0 / math.log2(index + 1)
    if idcg == 0:
        return 0.0
    return dcg / idcg


def evaluate_retrieval_case(case, *, retrieve_fn=retrieve):
    query = str(case.get("query") or "").strip()
    if not query:
        raise ValueError("retrieval evaluation case requires a non-empty query.")

    top_k = int(case.get("top_k") or 5)
    filters = case.get("filters") or {}
    query_variants = case.get("query_variants") or []
    target_type, targets = _expected_relevance_targets(case)

    started_at = perf_counter()
    results = retrieve_fn(
        query=query,
        filters=filters,
        top_k=top_k,
        query_variants=query_variants,
    )
    latency_ms = (perf_counter() - started_at) * 1000
    hits = _binary_relevance_hits(results, target_type, targets)

    return {
        "name": case.get("name") or query,
        "query": query,
        "filters": filters,
        "top_k": top_k,
        "query_variants": query_variants,
        "expected_target_type": target_type,
        "expected_targets": targets,
        "retrieved_chunk_ids": [result.get("chunk_id") for result in results],
        "retrieved_titles": [result.get("document_title") for result in results],
        "result_count": len(results),
        "recall_at_k": _recall_at_k(results, target_type, targets),
        "mrr": _mrr(hits),
        "ndcg_at_k": _ndcg_at_k(hits, len(targets)),
        "latency_ms": round(latency_ms, 2),
    }


def evaluate_retrieval_cases(cases, *, retrieve_fn=retrieve):
    case_results = [evaluate_retrieval_case(case, retrieve_fn=retrieve_fn) for case in cases]
    total = len(case_results)
    if total == 0:
        return {
            "total_cases": 0,
            "summary": {
                "recall_at_k": 0.0,
                "mrr": 0.0,
                "ndcg_at_k": 0.0,
                "average_latency_ms": 0.0,
            },
            "cases": [],
        }

    return {
        "total_cases": total,
        "summary": {
            "recall_at_k": round(sum(case["recall_at_k"] for case in case_results) / total, 4),
            "mrr": round(sum(case["mrr"] for case in case_results) / total, 4),
            "ndcg_at_k": round(sum(case["ndcg_at_k"] for case in case_results) / total, 4),
            "average_latency_ms": round(sum(case["latency_ms"] for case in case_results) / total, 2),
        },
        "cases": case_results,
    }


def evaluate_retrieval_fixture(path=None, *, retrieve_fn=retrieve):
    return evaluate_retrieval_cases(load_retrieval_cases(path), retrieve_fn=retrieve_fn)


# ---------------------------------------------------------------------------
# Generation quality evaluation (faithfulness + relevancy)
# ---------------------------------------------------------------------------


def _build_eval_llm():
    from rag.services.llamaindex_llm_adapter import FinModProLLMAdapter

    return FinModProLLMAdapter()


def evaluate_generation_case(case, *, retrieve_fn=retrieve, llm=None):
    from llama_index.core.evaluation import FaithfulnessEvaluator, RelevancyEvaluator

    query = str(case.get("query") or "").strip()
    if not query:
        raise ValueError("evaluation case requires a non-empty query.")

    top_k = int(case.get("top_k") or 5)
    filters = case.get("filters") or {}
    query_variants = case.get("query_variants") or []

    started_at = perf_counter()
    results = retrieve_fn(
        query=query,
        filters=filters,
        top_k=top_k,
        query_variants=query_variants,
    )
    retrieval_latency_ms = (perf_counter() - started_at) * 1000

    context_str = "\n\n".join(
        f"[{r.get('document_title', '')} - {r.get('page_label', '')}]\n{r.get('snippet', '')}"
        for r in results
    )

    eval_llm = llm or _build_eval_llm()

    answer_prompt = (
        f"Based on the following context, answer the question.\n\n"
        f"Context:\n{context_str}\n\n"
        f"Question: {query}\n\n"
        f"Answer:"
    )
    answer = eval_llm.complete(answer_prompt).text

    faithfulness_evaluator = FaithfulnessEvaluator(llm=eval_llm)
    faithfulness_result = faithfulness_evaluator.evaluate(
        query=query,
        response=answer,
        contexts=[context_str],
    )

    relevancy_evaluator = RelevancyEvaluator(llm=eval_llm)
    relevancy_result = relevancy_evaluator.evaluate(
        query=query,
        response=answer,
        contexts=[context_str],
    )

    return {
        "name": case.get("name") or query,
        "query": query,
        "answer": answer,
        "result_count": len(results),
        "retrieval_latency_ms": round(retrieval_latency_ms, 2),
        "faithfulness_score": faithfulness_result.score,
        "faithfulness_passing": faithfulness_result.passing,
        "relevancy_score": relevancy_result.score,
        "relevancy_passing": relevancy_result.passing,
    }


def evaluate_generation_cases(cases, *, retrieve_fn=retrieve, llm=None):
    eval_llm = llm or _build_eval_llm()
    case_results = [
        evaluate_generation_case(c, retrieve_fn=retrieve_fn, llm=eval_llm)
        for c in cases
    ]
    total = len(case_results)
    if total == 0:
        return {"total_cases": 0, "summary": {}, "cases": []}

    return {
        "total_cases": total,
        "summary": {
            "avg_faithfulness": round(
                sum(c["faithfulness_score"] for c in case_results) / total, 4
            ),
            "avg_relevancy": round(
                sum(c["relevancy_score"] for c in case_results) / total, 4
            ),
            "faithfulness_pass_rate": round(
                sum(1 for c in case_results if c["faithfulness_passing"]) / total, 4
            ),
            "relevancy_pass_rate": round(
                sum(1 for c in case_results if c["relevancy_passing"]) / total, 4
            ),
            "avg_retrieval_latency_ms": round(
                sum(c["retrieval_latency_ms"] for c in case_results) / total, 2
            ),
        },
        "cases": case_results,
    }


def evaluate_generation_fixture(path=None, *, retrieve_fn=retrieve, llm=None):
    return evaluate_generation_cases(
        load_retrieval_cases(path), retrieve_fn=retrieve_fn, llm=llm
    )
