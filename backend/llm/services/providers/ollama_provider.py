import json
import logging
import time
from urllib import error, request

from common.exceptions import UpstreamRateLimitError, UpstreamServiceError
from llm.models import ModelInvocationLog
from llm.services.model_invocation_log_service import record_model_invocation
from llm.services.providers.base import (
    BaseChatProvider,
    BaseEmbeddingProvider,
    ChatResult,
    EmbeddingResult,
    TokenUsage,
)


logger = logging.getLogger(__name__)


class OllamaApiMixin:
    provider_name = "ollama"

    def __init__(self, *, endpoint, model_name, options=None, model_config=None):
        self.endpoint = endpoint.rstrip("/")
        self.model_name = model_name
        self.options = options or {}
        self.model_config = model_config

    def _build_url(self, path):
        return f"{self.endpoint}{path}"

    def _post_json(self, path, payload, *, capability):
        url = self._build_url(path)
        body = json.dumps(payload).encode("utf-8")
        headers = {"Content-Type": "application/json"}
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
                request.Request(url, data=body, headers=headers, method="POST"),
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
            if exc.code == 429:
                raise UpstreamRateLimitError(
                    provider=self.provider_name,
                    retry_after=exc.headers.get("Retry-After"),
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
                "模型服务暂不可用。",
                status_code=503,
                code="llm_provider_unavailable",
                provider=self.provider_name,
            ) from exc

    def _usage_from_payload(self, payload) -> TokenUsage:
        request_tokens = int(payload.get("prompt_eval_count") or 0)
        response_tokens = int(payload.get("eval_count") or 0)
        total_tokens = int(payload.get("total_tokens") or (request_tokens + response_tokens))
        source = (
            ModelInvocationLog.TOKEN_SOURCE_PROVIDER
            if (request_tokens or response_tokens or total_tokens)
            else ModelInvocationLog.TOKEN_SOURCE_NONE
        )
        raw_usage = {
            "prompt_eval_count": request_tokens,
            "eval_count": response_tokens,
            "total_tokens": total_tokens,
        }
        return TokenUsage(
            request_tokens=request_tokens,
            response_tokens=response_tokens,
            total_tokens=total_tokens,
            source=source,
            raw=raw_usage,
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


class OllamaChatProvider(OllamaApiMixin, BaseChatProvider):
    def chat(self, *, messages, options=None, trace_id="", request_id=""):
        payload = {
            "model": self.model_name,
            "messages": messages,
            "stream": False,
        }
        merged_options = {**self.options, **(options or {})}
        if merged_options:
            payload["options"] = merged_options
        started_at = time.monotonic()
        try:
            response_payload = self._post_json("/api/chat", payload, capability="chat")
        except (UpstreamServiceError, UpstreamRateLimitError) as exc:
            self._record_failure(
                capability="chat",
                started_at=started_at,
                exc=exc,
                trace_id=trace_id,
                request_id=request_id,
            )
            raise
        message = response_payload.get("message") or {}
        content = message.get("content")
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
        usage = self._usage_from_payload(response_payload)
        result = ChatResult(
            content=content,
            usage=usage,
            finish_reason=response_payload.get("done_reason") or "",
            request_id=response_payload.get("context_id") or "",
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


class OllamaEmbeddingProvider(OllamaApiMixin, BaseEmbeddingProvider):
    def embed(self, *, texts, options=None, trace_id="", request_id=""):
        merged_options = {**self.options, **(options or {})}
        payload = {
            "model": self.model_name,
            "input": texts[0] if len(texts) == 1 else texts,
        }
        payload.update(merged_options)
        started_at = time.monotonic()
        try:
            response_payload = self._post_json("/api/embed", payload, capability="embedding")
        except (UpstreamServiceError, UpstreamRateLimitError) as exc:
            self._record_failure(
                capability="embedding",
                started_at=started_at,
                exc=exc,
                trace_id=trace_id,
                request_id=request_id,
            )
            raise
        raw_vectors = response_payload.get("embeddings")
        if not isinstance(raw_vectors, list) or not raw_vectors:
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
        vectors = raw_vectors if isinstance(raw_vectors[0], list) else [raw_vectors]
        usage = self._usage_from_payload(response_payload)
        result = EmbeddingResult(
            vectors=vectors,
            usage=usage,
            raw_response=response_payload,
        )
        self._record_success(
            capability="embedding",
            started_at=started_at,
            usage=usage,
            trace_id=trace_id,
            request_id=request_id,
        )
        return result
