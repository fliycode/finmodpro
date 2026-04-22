import json
import logging
import time
from urllib import error, request

from common.exceptions import UpstreamRateLimitError, UpstreamServiceError
from llm.services.providers.base import BaseEmbeddingProvider, BaseRerankProvider


logger = logging.getLogger(__name__)

_DASHSCOPE_RERANK_URL = (
    "https://dashscope.aliyuncs.com/api/v1/services/rerank/text-rerank/text-rerank"
)


class DashScopeApiMixin:
    provider_name = "dashscope"

    def __init__(self, *, endpoint, model_name, options=None):
        self.endpoint = endpoint.rstrip("/")
        self.model_name = model_name
        self.options = options or {}

    def _resolve_api_key(self, options=None):
        api_key = {**self.options, **(options or {})}.get("api_key")
        if not api_key:
            raise UpstreamServiceError(
                "DashScope API Key 未配置。",
                status_code=502,
                code="llm_provider_auth_failed",
                provider=self.provider_name,
            )
        return api_key

    def _build_headers(self, api_key):
        return {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    def _post_json(self, url, payload, *, options=None, capability):
        api_key = self._resolve_api_key(options)
        body = json.dumps(payload).encode("utf-8")
        started_at = time.monotonic()
        logger.info(
            "Calling %s provider",
            self.provider_name,
            extra={
                "provider": self.provider_name,
                "capability": capability,
                "model_name": self.model_name,
                "url": url,
            },
        )
        try:
            response = request.urlopen(
                request.Request(url, data=body, headers=self._build_headers(api_key), method="POST"),
                timeout=30,
            )
            response_payload = json.loads(response.read().decode("utf-8"))
            logger.info(
                "Completed %s provider call",
                self.provider_name,
                extra={
                    "provider": self.provider_name,
                    "capability": capability,
                    "model_name": self.model_name,
                    "duration_ms": int((time.monotonic() - started_at) * 1000),
                },
            )
            return response_payload
        except error.HTTPError as exc:
            response_body = exc.read().decode("utf-8", errors="ignore")
            logger.exception(
                "HTTP error from %s provider",
                self.provider_name,
                extra={
                    "provider": self.provider_name,
                    "capability": capability,
                    "model_name": self.model_name,
                    "status_code": exc.code,
                    "response_body": response_body[:500],
                },
            )
            if exc.code == 429:
                raise UpstreamRateLimitError(
                    provider=self.provider_name,
                    retry_after=exc.headers.get("Retry-After"),
                ) from exc
            lowered = response_body.lower()
            if exc.code in {401, 403} or "api key" in lowered or "unauthorized" in lowered:
                raise UpstreamServiceError(
                    "DashScope 认证失败。",
                    status_code=502,
                    code="llm_provider_auth_failed",
                    provider=self.provider_name,
                ) from exc
            raise UpstreamServiceError(
                "模型服务调用失败。",
                status_code=502,
                code="llm_provider_error",
                provider=self.provider_name,
            ) from exc
        except (error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            logger.exception(
                "Transport error from %s provider",
                self.provider_name,
                extra={
                    "provider": self.provider_name,
                    "capability": capability,
                    "model_name": self.model_name,
                },
            )
            raise UpstreamServiceError(
                "DashScope 服务暂不可用。",
                status_code=503,
                code="llm_provider_unavailable",
                provider=self.provider_name,
            ) from exc


class DashScopeEmbeddingProvider(DashScopeApiMixin, BaseEmbeddingProvider):
    """Calls DashScope OpenAI-compatible embedding endpoint."""

    def embed(self, *, texts, options=None):
        url = f"{self.endpoint}/embeddings"
        vectors = []
        for text in texts:
            payload = {"model": self.model_name, "input": text}
            response_payload = self._post_json(url, payload, options=options, capability="embedding")
            data = response_payload.get("data") or []
            embedding = (data[0] or {}).get("embedding")
            if not isinstance(embedding, list) or not embedding:
                raise UpstreamServiceError(
                    "模型服务返回了空向量。",
                    status_code=502,
                    code="llm_empty_embedding",
                    provider=self.provider_name,
                )
            vectors.append(embedding)
        return vectors


class DashScopeRerankProvider(DashScopeApiMixin, BaseRerankProvider):
    """Calls DashScope native rerank API."""

    def rerank(self, *, query, documents, top_n=None, options=None):
        parameters = {"return_documents": False}
        if top_n is not None:
            parameters["top_n"] = top_n

        payload = {
            "model": self.model_name,
            "input": {"query": query, "documents": documents},
            "parameters": parameters,
        }
        response_payload = self._post_json(
            _DASHSCOPE_RERANK_URL, payload, options=options, capability="rerank"
        )
        output = response_payload.get("output") or {}
        results = output.get("results") or []
        return [
            {"index": item["index"], "relevance_score": item["relevance_score"]}
            for item in results
        ]
