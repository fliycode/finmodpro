"""
重排序服务 —— 对检索结果进行重排序 (rerank)，提高结果的相关性。
类比 SpringBoot: 相当于 @Service 中的后处理层，
在检索获取候选结果后，通过 Rerank 模型重新评估每条结果与查询的相关性。

支持单查询重排序和多查询变体重排序（取每个结果在不同查询下的最高分数）。
"""

import logging

from common.exceptions import ProviderConfigurationError
from llm.services.model_config_service import get_active_model_config
from llm.models import ModelConfig


logger = logging.getLogger(__name__)


def rerank_results(results, query=None):
    """
    对检索结果进行重排序。

    如果有可用的 Rerank 模型配置，则调用 Rerank API 对每条结果的 snippet
    进行重排序，返回按 rerank_score 降序排列的结果。如果 Rerank 不可用，
    则按原始 score 降序排列作为降级方案。

    类比 SpringBoot: 相当于对 @Service 返回的 List<Result> 进行二次排序处理。

    参数:
        results (list[dict]): 待重排序的检索结果列表，每项应包含 "snippet" 字段。
        query (str, 可选): 重排序时使用的查询文本。

    返回:
        list[dict]: 重排序后的结果列表，按 rerank_score 或 score 降序排列。
    """
    if not results:
        return results

    if query:
        try:
            active_rerank_config = get_active_model_config(ModelConfig.CAPABILITY_RERANK)
        except Exception:
            active_rerank_config = None

        if active_rerank_config is not None:
            try:
                from llm.services.runtime_service import get_rerank_provider

                provider = get_rerank_provider()
                snippets = [item.get("snippet") or "" for item in results]
                rerank_output = provider.rerank(
                    query=query,
                    documents=snippets,
                    top_n=len(results),
                ).items
                scored = {entry["index"]: entry["relevance_score"] for entry in rerank_output}
                for idx, item in enumerate(results):
                    item["rerank_score"] = scored.get(idx, 0.0)
                return sorted(results, key=lambda item: item.get("rerank_score", 0.0), reverse=True)
            except ProviderConfigurationError:
                logger.warning("Rerank provider not configured; falling back to vector score.")
            except Exception:
                logger.exception("Rerank API call failed; falling back to vector score.")

    for item in results:
        if "rerank_score" not in item:
            item["rerank_score"] = item.get("score", 0.0)
    return sorted(results, key=lambda item: item.get("score", 0.0), reverse=True)


def rerank_with_variants(results, query_variants=None, fallback_query=None):
    """
    使用多查询变体对检索结果进行重排序。

    对每个查询变体分别调用 Rerank API，取每条结果在不同查询下的最高 relevance_score
    作为最终的 rerank_score。如果 Rerank 不可用，则直接用原始 score 作为 rerank_score。

    类比 SpringBoot: 相当于对多个查询变体并行调用 Rerank 服务，
    然后聚合每个文档的最佳分数。

    参数:
        results (list[dict]): 待重排序的检索结果列表，每项应包含 "snippet" 字段。
        query_variants (list[str] | None, 可选): 查询变体列表，用于多轮重排序。
        fallback_query (str, 可选): 当 query_variants 为空时的兜底查询文本。

    返回:
        list[dict]: 重排序后的结果列表，按 rerank_score 降序排列。
    """
    if not results:
        return results

    try:
        active_rerank_config = get_active_model_config(ModelConfig.CAPABILITY_RERANK)
    except Exception:
        active_rerank_config = None

    if active_rerank_config is None:
        for item in results:
            if "rerank_score" not in item:
                item["rerank_score"] = item.get("score", 0.0)
        return sorted(results, key=lambda item: item.get("rerank_score", 0.0), reverse=True)

    try:
        from llm.services.runtime_service import get_rerank_provider

        provider = get_rerank_provider()
        snippets = [item.get("snippet") or "" for item in results]
        queries = list(dict.fromkeys(
            [q for q in (query_variants or []) if q] + ([fallback_query] if fallback_query else [])
        ))
        if not queries:
            return sorted(results, key=lambda item: item.get("score", 0.0), reverse=True)

        best_scores = [0.0] * len(results)
        for q in queries:
            rerank_output = provider.rerank(
                query=q,
                documents=snippets,
                top_n=len(results),
            ).items
            for entry in rerank_output:
                idx = entry["index"]
                best_scores[idx] = max(best_scores[idx], entry["relevance_score"])

        for idx, item in enumerate(results):
            item["rerank_score"] = best_scores[idx]
        return sorted(results, key=lambda item: item.get("rerank_score", 0.0), reverse=True)
    except ProviderConfigurationError:
        logger.warning("Rerank provider not configured; falling back to vector score.")
    except Exception:
        logger.exception("Rerank API call failed; falling back to vector score.")

    for item in results:
        if "rerank_score" not in item:
            item["rerank_score"] = item.get("score", 0.0)
    return sorted(results, key=lambda item: item.get("rerank_score", 0.0), reverse=True)
