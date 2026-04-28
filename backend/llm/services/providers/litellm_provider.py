import json
import logging
import time
from urllib import error, request

from django.conf import settings

from common.exceptions import UpstreamRateLimitError, UpstreamServiceError
from llm.services.model_invocation_log_service import record_model_invocation
from llm.services.providers.base import BaseChatProvider, BaseEmbeddingProvider, BaseRerankProvider


logger = logging.getLogger(__name__)


class LiteLLMApiMixin:
    provider_name = "litellm"

    def __init__(self, *, endpoint, model_name, options=None, model_config=None):
        self.endpoint = endpoint.rstrip("/")
        self.model_name = model_name
        self.options = options or {}
        self.model_config = model_config

    def _resolve_options(self, options=None):
        return {**self.options, **(options or {})}

    def _resolve_api_key(self, options=None):
        api_key = settings.LITELLM_MASTER_KEY or self._resolve_options(options).get("api_key")
        if not api_key:
            raise UpstreamServiceError(
                "LiteLLM API Key 未配置。",
                status_code=502,
                code="llm_provider_auth_failed",
                provider=self.provider_name,
            )
        return api_key

    def _build_url(self, path):
        return f"{self.endpoint}{path}"

    def _build_headers(self, api_key):
        return {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    def _post_json(self, path, payload, *, options=None, capability):
        api_key = self._resolve_api_key(options)
        body = json.dumps(payload).encode("utf-8")
        url = self._build_url(path)
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
            lowered_body = response_body.lower()
            if exc.code == 429:
                raise UpstreamRateLimitError(
                    provider=self.provider_name,
                    retry_after=exc.headers.get("Retry-After"),
                ) from exc
            if exc.code in {401, 403} or "api key" in lowered_body or "unauthorized" in lowered_body:
                raise UpstreamServiceError(
                    "LiteLLM 认证失败。",
                    status_code=502,
                    code="llm_provider_auth_failed",
                    provider=self.provider_name,
                ) from exc
            if exc.code == 404 or "model" in lowered_body and "not" in lowered_body:
                raise UpstreamServiceError(
                    "LiteLLM 模型名称无效。",
                    status_code=502,
                    code="llm_provider_invalid_model",
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
                "LiteLLM 服务暂不可用。",
                status_code=503,
                code="llm_provider_unavailable",
                provider=self.provider_name,
            ) from exc


class LiteLLMChatProvider(LiteLLMApiMixin, BaseChatProvider):
    def chat(self, *, messages, options=None, trace_id="", request_id=""):
        merged_options = self._resolve_options(options)
        payload = {
            "model": self.model_name,
            "messages": messages,
            "stream": False,
        }
        if merged_options.get("temperature") is not None:
            payload["temperature"] = merged_options["temperature"]
        if merged_options.get("max_tokens") is not None:
            payload["max_tokens"] = merged_options["max_tokens"]
        started_at = time.monotonic()
        upstream_model = (
            (self.model_config.options or {}).get("litellm", {}).get("upstream_model")
            if self.model_config is not None
            else None
        ) or self.model_name
        try:
            response_payload = self._post_json(
                "/v1/chat/completions",
                payload,
                options=options,
                capability="chat",
            )
        except (UpstreamServiceError, UpstreamRateLimitError) as exc:
            if self.model_config is not None and self.model_config.pk is not None:
                try:
                    record_model_invocation(
                        model_config=self.model_config,
                        capability="chat",
                        alias=self.model_name,
                        upstream_model=upstream_model,
                        status="failed",
                        latency_ms=int((time.monotonic() - started_at) * 1000),
                        error_code=exc.code,
                        error_message=exc.message,
                        trace_id=trace_id,
                        request_id=request_id,
                    )
                except Exception:
                    logger.exception("Failed to record failed chat invocation log")
            raise
        latency_ms = int((time.monotonic() - started_at) * 1000)
        usage = response_payload.get("usage") or {}
        request_tokens = usage.get("prompt_tokens", 0)
        response_tokens = usage.get("completion_tokens", 0)
        choices = response_payload.get("choices") or []
        message = (choices[0] or {}).get("message") or {}
        content = message.get("content")
        if not content:
            if self.model_config is not None and self.model_config.pk is not None:
                try:
                    record_model_invocation(
                        model_config=self.model_config,
                        capability="chat",
                        alias=self.model_name,
                        upstream_model=upstream_model,
                        status="failed",
                        latency_ms=latency_ms,
                        error_code="llm_empty_response",
                        error_message="模型服务返回了空响应。",
                        trace_id=trace_id,
                        request_id=request_id,
                    )
                except Exception:
                    logger.exception("Failed to record empty-response chat invocation log")
            raise UpstreamServiceError(
                "模型服务返回了空响应。",
                status_code=502,
                code="llm_empty_response",
                provider=self.provider_name,
            )
        if self.model_config is not None and self.model_config.pk is not None:
            try:
                record_model_invocation(
                    model_config=self.model_config,
                    capability="chat",
                    alias=self.model_name,
                    upstream_model=upstream_model,
                    status="success",
                    latency_ms=latency_ms,
                    request_tokens=request_tokens,
                    response_tokens=response_tokens,
                    trace_id=trace_id,
                    request_id=request_id,
                )
            except Exception:
                logger.exception("Failed to record successful chat invocation log")
        return content

    def generate(self, *, messages, trace_id="", request_id="", options=None):
        """Backward-compatible alias for chat() that passes trace/request IDs."""
        return self.chat(messages=messages, options=options, trace_id=trace_id, request_id=request_id)

    def stream(self, *, messages, options=None):
        merged_options = self._resolve_options(options)
        payload = {
            "model": self.model_name,
            "messages": messages,
            "stream": True,
        }
        if merged_options.get("temperature") is not None:
            payload["temperature"] = merged_options["temperature"]
        if merged_options.get("max_tokens") is not None:
            payload["max_tokens"] = merged_options["max_tokens"]
        api_key = self._resolve_api_key(options)
        body = json.dumps(payload).encode("utf-8")
        url = self._build_url("/v1/chat/completions")
        try:
            response = request.urlopen(
                request.Request(url, data=body, headers=self._build_headers(api_key), method="POST"),
                timeout=30,
            )
            for raw_line in response:
                line = raw_line.decode("utf-8", errors="ignore").strip()
                if not line or not line.startswith("data:"):
                    continue
                data = line.removeprefix("data:").strip()
                if data == "[DONE]":
                    break
                try:
                    chunk_payload = json.loads(data)
                except json.JSONDecodeError:
                    continue
                choices = chunk_payload.get("choices") or []
                delta = (choices[0] or {}).get("delta") or {}
                content = delta.get("content")
                if content:
                    yield content
        except error.HTTPError as exc:
            response_body = exc.read().decode("utf-8", errors="ignore").lower()
            if exc.code == 429:
                raise UpstreamRateLimitError(
                    provider=self.provider_name,
                    retry_after=exc.headers.get("Retry-After"),
                ) from exc
            if exc.code in {401, 403} or "api key" in response_body or "unauthorized" in response_body:
                raise UpstreamServiceError(
                    "LiteLLM 认证失败。",
                    status_code=502,
                    code="llm_provider_auth_failed",
                    provider=self.provider_name,
                ) from exc
            raise UpstreamServiceError(
                "LiteLLM 服务暂不可用。",
                status_code=503,
                code="llm_provider_unavailable",
                provider=self.provider_name,
            ) from exc
        except (error.URLError, TimeoutError) as exc:
            raise UpstreamServiceError(
                "LiteLLM 服务暂不可用。",
                status_code=503,
                code="llm_provider_unavailable",
                provider=self.provider_name,
            ) from exc


class LiteLLMEmbeddingProvider(LiteLLMApiMixin, BaseEmbeddingProvider):
    def embed(self, *, texts, options=None, trace_id="", request_id=""):
        started_at = time.monotonic()
        merged_options = self._resolve_options(options)
        total_request_tokens = 0
        upstream_model = (
            (self.model_config.options or {}).get("litellm", {}).get("upstream_model")
            if self.model_config is not None
            else None
        ) or self.model_name
        try:
            payload = {
                "model": self.model_name,
                "input": texts[0] if len(texts) == 1 else texts,
                "encoding_format": merged_options.get("encoding_format") or "float",
            }
            response_payload = self._post_json(
                "/v1/embeddings",
                payload,
                options=options,
                capability="embedding",
            )
            usage = response_payload.get("usage") or {}
            total_request_tokens = usage.get("prompt_tokens", 0)
            data = response_payload.get("data") or []
            vectors = []
            for item in data:
                embedding = (item or {}).get("embedding")
                if not isinstance(embedding, list) or not embedding:
                    raise UpstreamServiceError(
                        "模型服务返回了空向量。",
                        status_code=502,
                        code="llm_empty_embedding",
                        provider=self.provider_name,
                    )
                vectors.append(embedding)
            if len(vectors) != len(texts):
                raise UpstreamServiceError(
                    "模型服务返回的向量数量不匹配。",
                    status_code=502,
                    code="llm_invalid_embedding_count",
                    provider=self.provider_name,
                )
        except (UpstreamServiceError, UpstreamRateLimitError) as exc:
            if self.model_config is not None and self.model_config.pk is not None:
                try:
                    record_model_invocation(
                        model_config=self.model_config,
                        capability="embedding",
                        alias=self.model_name,
                        upstream_model=upstream_model,
                        status="failed",
                        latency_ms=int((time.monotonic() - started_at) * 1000),
                        request_tokens=total_request_tokens,
                        response_tokens=0,
                        error_code=exc.code,
                        error_message=exc.message,
                        trace_id=trace_id,
                        request_id=request_id,
                    )
                except Exception:
                    logger.exception("Failed to record failed embedding invocation log")
            raise
        latency_ms = int((time.monotonic() - started_at) * 1000)
        if self.model_config is not None and self.model_config.pk is not None:
            try:
                record_model_invocation(
                    model_config=self.model_config,
                    capability="embedding",
                    alias=self.model_name,
                    upstream_model=upstream_model,
                    status="success",
                    latency_ms=latency_ms,
                    request_tokens=total_request_tokens,
                    response_tokens=0,
                    trace_id=trace_id,
                    request_id=request_id,
                )
            except Exception:
                logger.exception("Failed to record successful embedding invocation log")
        return vectors


class LiteLLMRerankProvider(LiteLLMApiMixin, BaseRerankProvider):
    def rerank(self, *, query, documents, top_n=None, options=None, trace_id="", request_id=""):
        payload = {
            "model": self.model_name,
            "query": query,
            "documents": documents,
        }
        if top_n is not None:
            payload["top_n"] = top_n

        started_at = time.monotonic()
        upstream_model = (
            (self.model_config.options or {}).get("litellm", {}).get("upstream_model")
            if self.model_config is not None
            else None
        ) or self.model_name
        try:
            response_payload = self._post_json(
                "/v1/rerank",
                payload,
                options=options,
                capability="rerank",
            )
        except (UpstreamServiceError, UpstreamRateLimitError) as exc:
            if self.model_config is not None and self.model_config.pk is not None:
                try:
                    record_model_invocation(
                        model_config=self.model_config,
                        capability="rerank",
                        alias=self.model_name,
                        upstream_model=upstream_model,
                        status="failed",
                        latency_ms=int((time.monotonic() - started_at) * 1000),
                        error_code=exc.code,
                        error_message=exc.message,
                        trace_id=trace_id,
                        request_id=request_id,
                    )
                except Exception:
                    logger.exception("Failed to record failed rerank invocation log")
            raise

        results = response_payload.get("results") or response_payload.get("data") or []
        normalized_results = [
            {
                "index": item["index"],
                "relevance_score": item["relevance_score"],
            }
            for item in results
            if isinstance(item, dict) and "index" in item and "relevance_score" in item
        ]
        if not normalized_results:
            raise UpstreamServiceError(
                "模型服务返回了空重排结果。",
                status_code=502,
                code="llm_empty_rerank",
                provider=self.provider_name,
            )

        if self.model_config is not None and self.model_config.pk is not None:
            try:
                record_model_invocation(
                    model_config=self.model_config,
                    capability="rerank",
                    alias=self.model_name,
                    upstream_model=upstream_model,
                    status="success",
                    latency_ms=int((time.monotonic() - started_at) * 1000),
                    trace_id=trace_id,
                    request_id=request_id,
                )
            except Exception:
                logger.exception("Failed to record successful rerank invocation log")
        return normalized_results
