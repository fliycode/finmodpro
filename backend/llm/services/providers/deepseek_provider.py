from common.exceptions import UpstreamServiceError
from llm.services.providers.base import BaseChatProvider


class DeepSeekChatProvider(BaseChatProvider):
    provider_name = "deepseek"

    def __init__(self, *, endpoint, model_name, options=None):
        self.endpoint = (endpoint or "").rstrip("/")
        self.model_name = model_name
        self.options = options or {}
        self.api_key = self.options.get("api_key") or self.options.get("apiKey") or ""

        if not self.endpoint:
            raise UpstreamServiceError(
                "DeepSeek endpoint 未配置。",
                status_code=500,
                code="llm_misconfigured",
                provider=self.provider_name,
            )

        if not self.api_key:
            raise UpstreamServiceError(
                "DeepSeek API Key 未配置。",
                status_code=500,
                code="llm_misconfigured",
                provider=self.provider_name,
            )

    def chat(self, *, messages, options=None):
        raise UpstreamServiceError(
            "DeepSeek provider 占位实现尚未启用真实调用。",
            status_code=501,
            code="llm_provider_not_implemented",
            provider=self.provider_name,
        )
