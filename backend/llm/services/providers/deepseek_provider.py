"""
DeepSeek Provider（类比 SpringBoot 中对接 DeepSeek API 的 @Service 实现）。

DeepSeekChatProvider 直接继承自 OpenAICompatibleChatProvider，因为 DeepSeek 的
Chat API 完全兼容 OpenAI 的 /v1/chat/completions 格式。
默认 endpoint 为 https://api.deepseek.com。

类比 SpringBoot 中一个只需覆盖默认配置的简单 Bean 实现。
"""
from llm.services.providers.openai_compatible_provider import OpenAICompatibleChatProvider


class DeepSeekChatProvider(OpenAICompatibleChatProvider):
    """DeepSeek Chat Provider。

    继承自 OpenAICompatibleChatProvider，使用 DeepSeek 的默认 API endpoint。
    支持 DeepSeek-V3、DeepSeek-R1 等模型。
    """
    provider_name = "deepseek"

    def __init__(self, *, endpoint, model_name, options=None, model_config=None):
        """初始化 DeepSeek Chat Provider。

        参数:
            endpoint: str，API 端点地址（为 None 或空时使用默认 https://api.deepseek.com）。
            model_name: str，模型名称（如 deepseek-chat、deepseek-reasoner）。
            options: dict 或 None，额外选项（如 api_key、temperature 等）。
            model_config: ModelConfig 实例或 None。
        """
        super().__init__(
            endpoint=(endpoint or "https://api.deepseek.com"),
            model_name=model_name,
            options=options,
            model_config=model_config,
        )
