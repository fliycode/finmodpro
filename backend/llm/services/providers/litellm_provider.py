import json
import logging
import time
from urllib import error, request

from common.exceptions import UpstreamRateLimitError, UpstreamServiceError
from llm.services.providers.base import BaseChatProvider, BaseEmbeddingProvider


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
        api_key = self._resolve_options(options).get("api_key")
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
    def chat(self, *, messages, options=None):
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
        response_payload = self._post_json(
            "/v1/chat/completions",
            payload,
            options=options,
            capability="chat",
        )
        choices = response_payload.get("choices") or []
        message = (choices[0] or {}).get("message") or {}
        content = message.get("content")
        if not content:
            raise UpstreamServiceError(
                "模型服务返回了空响应。",
                status_code=502,
                code="llm_empty_response",
                provider=self.provider_name,
            )
        return content

    def generate(self, *, messages, trace_id="", request_id="", options=None):
        """Like chat() but records a ModelInvocationLog with token counts."""
        from llm.services.model_invocation_log_service import record_model_invocation

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
        response_payload = self._post_json(
            "/v1/chat/completions",
            payload,
            options=options,
            capability="chat",
        )
        latency_ms = int((time.monotonic() - started_at) * 1000)
        usage = response_payload.get("usage") or {}
        request_tokens = usage.get("prompt_tokens", 0)
        response_tokens = usage.get("completion_tokens", 0)
        choices = response_payload.get("choices") or []
        message = (choices[0] or {}).get("message") or {}
        content = message.get("content")
        if not content:
            raise UpstreamServiceError(
                "模型服务返回了空响应。",
                status_code=502,
                code="llm_empty_response",
                provider=self.provider_name,
            )
        if self.model_config is not None and self.model_config.pk:
            record_model_invocation(
                model_config=self.model_config,
                capability="chat",
                alias=self.model_name,
                upstream_model=self.model_name,
                status="success",
                latency_ms=latency_ms,
                request_tokens=request_tokens,
                response_tokens=response_tokens,
                trace_id=trace_id,
                request_id=request_id,
            )
        return content

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
    def embed(self, *, texts, options=None):
        vectors = []
        for text in texts:
            payload = {"model": self.model_name, "input": text}
            response_payload = self._post_json(
                "/v1/embeddings",
                payload,
                options=options,
                capability="embedding",
            )
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
