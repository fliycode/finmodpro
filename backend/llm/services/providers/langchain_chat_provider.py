from common.exceptions import UpstreamServiceError
from llm.services.providers.base import BaseChatProvider

try:
    from langchain.chat_models import init_chat_model
except ImportError:
    init_chat_model = None


class LangChainChatProvider(BaseChatProvider):
    provider_name = "langchain"

    def __init__(self, *, endpoint, model_name, options=None):
        self.endpoint = (endpoint or "").rstrip("/")
        self.model_name = model_name
        self.options = options or {}
        self.model_provider = (
            self.options.get("model_provider") or self.options.get("modelProvider") or ""
        )

        if not self.model_provider:
            raise UpstreamServiceError(
                "LangChain model_provider 未配置。",
                status_code=500,
                code="llm_misconfigured",
                provider=self.provider_name,
            )

    def _build_model(self, runtime_options=None):
        if init_chat_model is None:
            raise UpstreamServiceError(
                "LangChain dependencies are not installed. Install backend requirements to enable LangChain adapters.",
                status_code=500,
                code="llm_dependency_missing",
                provider=self.provider_name,
            )

        merged_options = {**self.options, **(runtime_options or {})}
        kwargs = {
            "model": self.model_name,
            "model_provider": self.model_provider,
        }
        if self.endpoint:
            kwargs["base_url"] = self.endpoint

        for key, value in merged_options.items():
            if key in {"model_provider", "modelProvider"}:
                continue
            kwargs[key] = value

        return init_chat_model(**kwargs)

    def chat(self, *, messages, options=None):
        response = self._build_model(runtime_options=options).invoke(messages)
        if isinstance(response, str):
            return response

        content = getattr(response, "content", None)
        if isinstance(content, list):
            parts = [part.get("text", "") for part in content if isinstance(part, dict)]
            content = "".join(parts)
        if content:
            return content

        raise UpstreamServiceError(
            "模型服务返回了空响应。",
            status_code=502,
            code="llm_empty_response",
            provider=self.provider_name,
        )
