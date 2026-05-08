import logging

from common.exceptions import ProviderConfigurationError
from llm.services.model_config_service import get_active_model_config
from llm.models import ModelConfig


logger = logging.getLogger(__name__)


def rerank_results(results, query=None):
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
                )
                scored = {entry["index"]: entry["relevance_score"] for entry in rerank_output}
                for idx, item in enumerate(results):
                    item["rerank_score"] = scored.get(idx, 0.0)
                return sorted(results, key=lambda item: item.get("rerank_score", 0.0), reverse=True)
            except ProviderConfigurationError:
                logger.warning("Rerank provider not configured; falling back to vector score.")
            except Exception:
                logger.exception("Rerank API call failed; falling back to vector score.")

    return sorted(results, key=lambda item: item.get("score", 0.0), reverse=True)


def rerank_with_variants(results, query_variants=None, fallback_query=None):
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
            )
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

    return sorted(results, key=lambda item: item.get("score", 0.0), reverse=True)
