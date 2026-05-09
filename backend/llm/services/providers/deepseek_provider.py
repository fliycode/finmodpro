from llm.services.providers.openai_compatible_provider import OpenAICompatibleChatProvider


class DeepSeekChatProvider(OpenAICompatibleChatProvider):
    provider_name = "deepseek"

    def __init__(self, *, endpoint, model_name, options=None, model_config=None):
        super().__init__(
            endpoint=(endpoint or "https://api.deepseek.com"),
            model_name=model_name,
            options=options,
            model_config=model_config,
        )
