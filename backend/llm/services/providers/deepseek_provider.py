from common.exceptions import UpstreamRateLimitError, UpstreamServiceError
from llm.services.providers.base import BaseChatProvider

try:
    from langchain.chat_models import init_chat_model
except ImportError:  # pragma: no cover - exercised in runtime env
    init_chat_model = None


class DeepSeekChatProvider(BaseChatProvider):
    provider_name = "deepseek"

    def __init__(self, *, endpoint, model_name, options=None):
        self.endpoint = (endpoint or "https://api.deepseek.com").rstrip("/")
        self.model_name = model_name
        self.options = options or {}

    def _ensure_dependency(self):
        if init_chat_model is None:
            raise UpstreamServiceError(
                "DeepSeek provider 依赖未安装。",
                status_code=503,
                code="llm_provider_dependency_missing",
                provider=self.provider_name,
            )

    def _resolve_options(self, options=None):
        merged_options = {**self.options, **(options or {})}
        if not merged_options.get("api_key"):
            raise UpstreamServiceError(
                "DeepSeek API Key 未配置。",
                status_code=502,
                code="llm_provider_auth_failed",
                provider=self.provider_name,
            )
        return merged_options

    def _build_client(self, options=None):
        self._ensure_dependency()
        resolved_options = self._resolve_options(options)
        return init_chat_model(
            model=self.model_name,
            model_provider="openai",
            api_key=resolved_options.get("api_key"),
            base_url=f"{self.endpoint}/v1",
            temperature=resolved_options.get("temperature"),
            max_tokens=resolved_options.get("max_tokens"),
        )

    def _map_upstream_error(self, exc):
        message = str(exc).lower()
        if "429" in message or "rate limit" in message or "too many requests" in message:
            raise UpstreamRateLimitError(provider=self.provider_name) from exc
        if "401" in message or "api key" in message or "authentication" in message:
            raise UpstreamServiceError(
                "DeepSeek 认证失败。",
                status_code=502,
                code="llm_provider_auth_failed",
                provider=self.provider_name,
            ) from exc
        if "model" in message and "not" in message and "found" in message:
            raise UpstreamServiceError(
                "DeepSeek 模型名称无效。",
                status_code=502,
                code="llm_provider_invalid_model",
                provider=self.provider_name,
            ) from exc
        raise UpstreamServiceError(
            "DeepSeek 服务暂不可用。",
            status_code=503,
            code="llm_provider_unavailable",
            provider=self.provider_name,
        ) from exc

    def chat(self, *, messages, options=None):
        client = self._build_client(options)
        try:
            response = client.invoke(messages)
        except Exception as exc:  # noqa: BLE001
            self._map_upstream_error(exc)

        content = getattr(response, "content", None)
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
        client = self._build_client(options)
        try:
            for chunk in client.stream(messages):
                content = getattr(chunk, "content", None)
                if isinstance(content, list):
                    content = "".join(str(item) for item in content)
                if content:
                    yield content
        except Exception as exc:  # noqa: BLE001
            self._map_upstream_error(exc)
