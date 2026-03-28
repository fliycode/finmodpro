import json
import logging
import time
from urllib import error, request

from common.exceptions import UpstreamRateLimitError, UpstreamServiceError
from llm.services.providers.base import BaseChatProvider, BaseEmbeddingProvider


logger = logging.getLogger(__name__)


class OllamaApiMixin:
    provider_name = "ollama"

    def __init__(self, *, endpoint, model_name, options=None):
        self.endpoint = endpoint.rstrip("/")
        self.model_name = model_name
        self.options = options or {}

    def _build_url(self, path):
        return f"{self.endpoint}{path}"

    def _post_json(self, path, payload, *, capability):
        url = self._build_url(path)
        body = json.dumps(payload).encode("utf-8")
        headers = {"Content-Type": "application/json"}
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
                request.Request(url, data=body, headers=headers, method="POST"),
                timeout=30,
            )
            payload = json.loads(response.read().decode("utf-8"))
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
            return payload
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
                status_code=502,
                code="llm_provider_unavailable",
                provider=self.provider_name,
            ) from exc


class OllamaChatProvider(OllamaApiMixin, BaseChatProvider):
    def chat(self, *, messages, options=None):
        payload = {
            "model": self.model_name,
            "messages": messages,
            "stream": False,
        }
        merged_options = {**self.options, **(options or {})}
        if merged_options:
            payload["options"] = merged_options
        response_payload = self._post_json("/api/chat", payload, capability="chat")
        message = response_payload.get("message") or {}
        content = message.get("content")
        if not content:
            raise UpstreamServiceError(
                "模型服务返回了空响应。",
                status_code=502,
                code="llm_empty_response",
                provider=self.provider_name,
            )
        return content


class OllamaEmbeddingProvider(OllamaApiMixin, BaseEmbeddingProvider):
    def embed(self, *, texts, options=None):
        merged_options = {**self.options, **(options or {})}
        embeddings = []
        for text in texts:
            payload = {
                "model": self.model_name,
                "input": text,
            }
            payload.update(merged_options)
            response_payload = self._post_json("/api/embed", payload, capability="embedding")
            vector = response_payload.get("embeddings")
            if not isinstance(vector, list) or not vector:
                raise UpstreamServiceError(
                    "模型服务返回了空向量。",
                    status_code=502,
                    code="llm_empty_embedding",
                    provider=self.provider_name,
                )
            first_vector = vector[0]
            if not isinstance(first_vector, list):
                raise UpstreamServiceError(
                    "模型服务返回了非法向量格式。",
                    status_code=502,
                    code="llm_invalid_embedding",
                    provider=self.provider_name,
                )
            embeddings.append(first_vector)
        return embeddings
