import json
import logging
import time
from urllib import error, request

from common.exceptions import UpstreamRateLimitError, UpstreamServiceError
from llm.services.providers.base import BaseChatProvider


logger = logging.getLogger(__name__)


class DeepSeekChatProvider(BaseChatProvider):
    provider_name = "deepseek"

    def __init__(self, *, endpoint, model_name, options=None):
        self.endpoint = (endpoint or "https://api.deepseek.com").rstrip("/")
        self.model_name = model_name
        self.options = options or {}

    def _resolve_options(self, options=None):
        merged_options = {**self.options, **(options or {})}
        api_key = merged_options.get("api_key")
        if not api_key:
            raise UpstreamServiceError(
                "DeepSeek API Key 未配置。",
                status_code=502,
                code="llm_provider_auth_failed",
                provider=self.provider_name,
            )
        return merged_options

    def _build_url(self):
        return f"{self.endpoint}/v1/chat/completions"

    def _build_headers(self, api_key):
        return {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    def _build_payload(self, messages, options=None, *, stream=False):
        merged_options = self._resolve_options(options)
        payload = {
            "model": self.model_name,
            "messages": messages,
            "stream": stream,
        }
        if merged_options.get("temperature") is not None:
            payload["temperature"] = merged_options.get("temperature")
        if merged_options.get("max_tokens") is not None:
            payload["max_tokens"] = merged_options.get("max_tokens")
        return payload, merged_options

    def _request_json(self, *, payload, api_key):
        body = json.dumps(payload).encode("utf-8")
        started_at = time.monotonic()
        url = self._build_url()
        logger.info(
            "Calling %s provider",
            self.provider_name,
            extra={
                "provider": self.provider_name,
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
            if exc.code in {401, 403} or "api key" in response_body.lower():
                raise UpstreamServiceError(
                    "DeepSeek 认证失败。",
                    status_code=502,
                    code="llm_provider_auth_failed",
                    provider=self.provider_name,
                ) from exc
            if exc.code == 404 or "model" in response_body.lower() and "not" in response_body.lower():
                raise UpstreamServiceError(
                    "DeepSeek 模型名称无效。",
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
                    "model_name": self.model_name,
                },
            )
            raise UpstreamServiceError(
                "DeepSeek 服务暂不可用。",
                status_code=503,
                code="llm_provider_unavailable",
                provider=self.provider_name,
            ) from exc

    def _extract_content(self, response_payload):
        choices = response_payload.get("choices") if isinstance(response_payload, dict) else None
        if not isinstance(choices, list) or not choices:
            return None

        first_choice = choices[0] or {}
        message = first_choice.get("message") or {}
        content = message.get("content")
        if content:
            return content

        delta = first_choice.get("delta") or {}
        content = delta.get("content")
        if content:
            return content

        return None

    def chat(self, *, messages, options=None):
        payload, resolved_options = self._build_payload(messages, options, stream=False)
        response_payload = self._request_json(payload=payload, api_key=resolved_options["api_key"])
        content = self._extract_content(response_payload)
        if isinstance(content, list):
            content = "".join(str(item) for item in content)
        if not content:
            raise UpstreamServiceError(
                "模型服务返回了空响应。",
                status_code=502,
                code="llm_empty_response",
                provider=self.provider_name,
            )
        return content

    def stream(self, *, messages, options=None):
        payload, resolved_options = self._build_payload(messages, options, stream=True)
        body = json.dumps(payload).encode("utf-8")
        url = self._build_url()
        try:
            response = request.urlopen(
                request.Request(
                    url,
                    data=body,
                    headers=self._build_headers(resolved_options["api_key"]),
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
                content = self._extract_content(chunk_payload)
                if isinstance(content, list):
                    content = "".join(str(item) for item in content)
                if content:
                    yield content
        except error.HTTPError as exc:
            response_body = exc.read().decode("utf-8", errors="ignore")
            if exc.code == 429:
                raise UpstreamRateLimitError(
                    provider=self.provider_name,
                    retry_after=exc.headers.get("Retry-After"),
                ) from exc
            if exc.code in {401, 403} or "api key" in response_body.lower():
                raise UpstreamServiceError(
                    "DeepSeek 认证失败。",
                    status_code=502,
                    code="llm_provider_auth_failed",
                    provider=self.provider_name,
                ) from exc
            raise UpstreamServiceError(
                "DeepSeek 服务暂不可用。",
                status_code=503,
                code="llm_provider_unavailable",
                provider=self.provider_name,
            ) from exc
        except (error.URLError, TimeoutError) as exc:
            raise UpstreamServiceError(
                "DeepSeek 服务暂不可用。",
                status_code=503,
                code="llm_provider_unavailable",
                provider=self.provider_name,
            ) from exc
