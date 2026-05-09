import json
import logging
import os
import time
from urllib import error, request

from common.exceptions import UpstreamRateLimitError, UpstreamServiceError
from llm.models import ModelInvocationLog
from llm.services.model_invocation_log_service import record_model_invocation
from llm.services.providers.base import (
    BaseChatProvider,
    BaseEmbeddingProvider,
    BaseRerankProvider,
    ChatResult,
    EmbeddingResult,
    RerankResult,
    TokenUsage,
)


logger = logging.getLogger(__name__)
TRANSPORT_RETRY_ATTEMPTS = 3
_PROVIDER_API_KEY_ENV_VARS = {
    "deepseek": "DEEPSEEK_API_KEY",
    "dashscope": "DASHSCOPE_API_KEY",
    "openai_compatible": "OPENAI_API_KEY",
}


class OpenAICompatibleApiMixin:
    provider_name = "openai_compatible"

    def __init__(self, *, endpoint, model_name, options=None, model_config=None):
        self.endpoint = endpoint.rstrip("/")
        self.model_name = model_name
        self.options = options or {}
        self.model_config = model_config

    def _resolve_options(self, options=None):
        merged_options = {**self.options, **(options or {})}
        api_key = merged_options.get("api_key")
        if not api_key:
            env_var_name = _PROVIDER_API_KEY_ENV_VARS.get(self.provider_name)
            if env_var_name:
                api_key = os.environ.get(env_var_name, "").strip()
        if api_key:
            merged_options["api_key"] = api_key
        if not api_key:
            raise UpstreamServiceError(
                "模型 API Key 未配置。",
                status_code=502,
                code="llm_provider_auth_failed",
                provider=self.provider_name,
            )
        return merged_options

    def _api_base(self):
        if self.endpoint.endswith("/v1"):
            return self.endpoint
        return f"{self.endpoint}/v1"

    def _build_url(self, path):
        return f"{self._api_base()}{path}"

    def _build_headers(self, api_key):
        return {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    def _usage_from_payload(self, payload) -> TokenUsage:
        usage = (payload or {}).get("usage") or {}
        request_tokens = int(usage.get("prompt_tokens") or usage.get("input_tokens") or 0)
        response_tokens = int(usage.get("completion_tokens") or usage.get("output_tokens") or 0)
        total_tokens = int(usage.get("total_tokens") or (request_tokens + response_tokens))
        source = (
            ModelInvocationLog.TOKEN_SOURCE_PROVIDER
            if (request_tokens or response_tokens or total_tokens)
            else ModelInvocationLog.TOKEN_SOURCE_NONE
        )
        return TokenUsage(
            request_tokens=request_tokens,
            response_tokens=response_tokens,
            total_tokens=total_tokens,
            source=source,
            raw=dict(usage),
        )

    def _record_success(self, *, capability, started_at, usage, trace_id="", request_id="", provider_request_id=""):
        if self.model_config is None or self.model_config.pk is None:
            return
        try:
            record_model_invocation(
                model_config=self.model_config,
                capability=capability,
                alias=self.model_config.name,
                upstream_model=self.model_name,
                status=ModelInvocationLog.STATUS_SUCCESS,
                latency_ms=int((time.monotonic() - started_at) * 1000),
                usage=usage,
                trace_id=trace_id,
                request_id=request_id,
                provider_request_id=provider_request_id,
            )
        except Exception:
            logger.exception("Failed to record successful %s invocation log", capability)

    def _record_failure(self, *, capability, started_at, exc, trace_id="", request_id=""):
        if self.model_config is None or self.model_config.pk is None:
            return
        try:
            record_model_invocation(
                model_config=self.model_config,
                capability=capability,
                alias=self.model_config.name,
                upstream_model=self.model_name,
                status=ModelInvocationLog.STATUS_FAILED,
                latency_ms=int((time.monotonic() - started_at) * 1000),
                error_code=exc.code,
                error_message=exc.message,
                trace_id=trace_id,
                request_id=request_id,
            )
        except Exception:
            logger.exception("Failed to record failed %s invocation log", capability)

    def _post_json(self, path, payload, *, options=None, capability):
        resolved_options = self._resolve_options(options)
        body = json.dumps(payload).encode("utf-8")
        url = self._build_url(path)
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
        for attempt in range(1, TRANSPORT_RETRY_ATTEMPTS + 1):
            try:
                response = request.urlopen(
                    request.Request(url, data=body, headers=self._build_headers(resolved_options["api_key"]), method="POST"),
                    timeout=30,
                )
                return json.loads(response.read().decode("utf-8"))
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
                        "模型服务认证失败。",
                        status_code=502,
                        code="llm_provider_auth_failed",
                        provider=self.provider_name,
                    ) from exc
                if exc.code == 404 or ("model" in lowered_body and "not" in lowered_body):
                    raise UpstreamServiceError(
                        "模型名称无效。",
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
            except (error.URLError, TimeoutError) as exc:
                if attempt < TRANSPORT_RETRY_ATTEMPTS:
                    logger.warning(
                        "Retrying %s provider call after transport error",
                        self.provider_name,
                        extra={
                            "provider": self.provider_name,
                            "capability": capability,
                            "model_name": self.model_name,
                            "attempt": attempt,
                        },
                    )
                    continue
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
                    "模型服务暂不可用。",
                    status_code=503,
                    code="llm_provider_unavailable",
                    provider=self.provider_name,
                ) from exc
            except json.JSONDecodeError as exc:
                logger.exception(
                    "JSON decode error from %s provider",
                    self.provider_name,
                    extra={
                        "provider": self.provider_name,
                        "capability": capability,
                        "model_name": self.model_name,
                    },
                )
                raise UpstreamServiceError(
                    "模型服务返回格式非法。",
                    status_code=502,
                    code="llm_provider_invalid_response",
                    provider=self.provider_name,
                ) from exc


class OpenAICompatibleChatProvider(OpenAICompatibleApiMixin, BaseChatProvider):
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
        try:
            response_payload = self._post_json(
                "/chat/completions",
                payload,
                options=options,
                capability="chat",
            )
        except (UpstreamServiceError, UpstreamRateLimitError) as exc:
            self._record_failure(
                capability="chat",
                started_at=started_at,
                exc=exc,
                trace_id=trace_id,
                request_id=request_id,
            )
            raise
        usage = self._usage_from_payload(response_payload)
        choices = response_payload.get("choices") or []
        message = (choices[0] or {}).get("message") or {}
        content = message.get("content")
        if isinstance(content, list):
            content = "".join(str(item) for item in content)
        if not content:
            exc = UpstreamServiceError(
                "模型服务返回了空响应。",
                status_code=502,
                code="llm_empty_response",
                provider=self.provider_name,
            )
            self._record_failure(
                capability="chat",
                started_at=started_at,
                exc=exc,
                trace_id=trace_id,
                request_id=request_id,
            )
            raise exc
        result = ChatResult(
            content=content,
            usage=usage,
            finish_reason=(choices[0] or {}).get("finish_reason") or "",
            request_id=response_payload.get("id") or "",
            raw_response=response_payload,
        )
        self._record_success(
            capability="chat",
            started_at=started_at,
            usage=usage,
            trace_id=trace_id,
            request_id=request_id,
            provider_request_id=result.request_id,
        )
        return result

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
        body = json.dumps(payload).encode("utf-8")
        url = self._build_url("/chat/completions")
        try:
            response = request.urlopen(
                request.Request(
                    url,
                    data=body,
                    headers=self._build_headers(merged_options["api_key"]),
                    method="POST",
                ),
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
                    "模型服务认证失败。",
                    status_code=502,
                    code="llm_provider_auth_failed",
                    provider=self.provider_name,
                ) from exc
            raise UpstreamServiceError(
                "模型服务暂不可用。",
                status_code=503,
                code="llm_provider_unavailable",
                provider=self.provider_name,
            ) from exc
        except (error.URLError, TimeoutError) as exc:
            raise UpstreamServiceError(
                "模型服务暂不可用。",
                status_code=503,
                code="llm_provider_unavailable",
                provider=self.provider_name,
            ) from exc


class OpenAICompatibleEmbeddingProvider(OpenAICompatibleApiMixin, BaseEmbeddingProvider):
    def embed(self, *, texts, options=None, trace_id="", request_id=""):
        started_at = time.monotonic()
        merged_options = self._resolve_options(options)
        payload = {
            "model": self.model_name,
            "input": texts[0] if len(texts) == 1 else texts,
            "encoding_format": merged_options.get("encoding_format") or "float",
        }
        try:
            response_payload = self._post_json(
                "/embeddings",
                payload,
                options=options,
                capability="embedding",
            )
        except (UpstreamServiceError, UpstreamRateLimitError) as exc:
            self._record_failure(
                capability="embedding",
                started_at=started_at,
                exc=exc,
                trace_id=trace_id,
                request_id=request_id,
            )
            raise
        data = response_payload.get("data") or []
        vectors = []
        for item in data:
            embedding = (item or {}).get("embedding")
            if not isinstance(embedding, list) or not embedding:
                exc = UpstreamServiceError(
                    "模型服务返回了空向量。",
                    status_code=502,
                    code="llm_empty_embedding",
                    provider=self.provider_name,
                )
                self._record_failure(
                    capability="embedding",
                    started_at=started_at,
                    exc=exc,
                    trace_id=trace_id,
                    request_id=request_id,
                )
                raise exc
            vectors.append(embedding)
        if len(vectors) != len(texts):
            exc = UpstreamServiceError(
                "模型服务返回的向量数量不匹配。",
                status_code=502,
                code="llm_invalid_embedding_count",
                provider=self.provider_name,
            )
            self._record_failure(
                capability="embedding",
                started_at=started_at,
                exc=exc,
                trace_id=trace_id,
                request_id=request_id,
            )
            raise exc
        usage = self._usage_from_payload(response_payload)
        result = EmbeddingResult(
            vectors=vectors,
            usage=usage,
            request_id=response_payload.get("id") or "",
            raw_response=response_payload,
        )
        self._record_success(
            capability="embedding",
            started_at=started_at,
            usage=usage,
            trace_id=trace_id,
            request_id=request_id,
            provider_request_id=result.request_id,
        )
        return result


class OpenAICompatibleRerankProvider(OpenAICompatibleApiMixin, BaseRerankProvider):
    def rerank(self, *, query, documents, top_n=None, options=None, trace_id="", request_id=""):
        payload = {
            "model": self.model_name,
            "query": query,
            "documents": documents,
        }
        if top_n is not None:
            payload["top_n"] = top_n
        started_at = time.monotonic()
        try:
            response_payload = self._post_json(
                "/rerank",
                payload,
                options=options,
                capability="rerank",
            )
        except (UpstreamServiceError, UpstreamRateLimitError) as exc:
            self._record_failure(
                capability="rerank",
                started_at=started_at,
                exc=exc,
                trace_id=trace_id,
                request_id=request_id,
            )
            raise
        raw_items = response_payload.get("results") or response_payload.get("data") or []
        items = [
            {
                "index": item["index"],
                "relevance_score": item["relevance_score"],
            }
            for item in raw_items
            if isinstance(item, dict) and "index" in item and "relevance_score" in item
        ]
        if not items:
            exc = UpstreamServiceError(
                "模型服务返回了空重排结果。",
                status_code=502,
                code="llm_empty_rerank",
                provider=self.provider_name,
            )
            self._record_failure(
                capability="rerank",
                started_at=started_at,
                exc=exc,
                trace_id=trace_id,
                request_id=request_id,
            )
            raise exc
        usage = self._usage_from_payload(response_payload)
        result = RerankResult(
            items=items,
            usage=usage,
            request_id=response_payload.get("id") or "",
            raw_response=response_payload,
        )
        self._record_success(
            capability="rerank",
            started_at=started_at,
            usage=usage,
            trace_id=trace_id,
            request_id=request_id,
            provider_request_id=result.request_id,
        )
        return result
