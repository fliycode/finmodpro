from llm.models import ModelConfig
from llm.services.model_config_service import get_active_model_config
from llm.services.providers.deepseek_provider import DeepSeekChatProvider
from llm.services.providers.langchain_chat_provider import LangChainChatProvider
from llm.services.providers.langchain_structured_output import (
    LangChainStructuredOutputProvider,
)
from llm.services.providers.ollama_provider import (
    OllamaChatProvider,
    OllamaEmbeddingProvider,
)


def _build_provider(model_config):
    if model_config.provider == ModelConfig.PROVIDER_OLLAMA:
        if model_config.capability == ModelConfig.CAPABILITY_CHAT:
            return OllamaChatProvider(
                endpoint=model_config.endpoint,
                model_name=model_config.model_name,
                options=model_config.options,
            )

        if model_config.capability == ModelConfig.CAPABILITY_EMBEDDING:
            return OllamaEmbeddingProvider(
                endpoint=model_config.endpoint,
                model_name=model_config.model_name,
                options=model_config.options,
            )

        raise ValueError(f"不支持的 capability: {model_config.capability}")

    if model_config.provider == ModelConfig.PROVIDER_DEEPSEEK:
        if model_config.capability == ModelConfig.CAPABILITY_CHAT:
            return DeepSeekChatProvider(
                endpoint=model_config.endpoint,
                model_name=model_config.model_name,
                options=model_config.options,
            )

        raise ValueError(f"不支持的 capability: {model_config.capability}")

    if model_config.provider == ModelConfig.PROVIDER_LANGCHAIN:
        if model_config.capability == ModelConfig.CAPABILITY_CHAT:
            return LangChainChatProvider(
                endpoint=model_config.endpoint,
                model_name=model_config.model_name,
                options=model_config.options,
            )

        if model_config.capability == ModelConfig.CAPABILITY_EMBEDDING:
            raise ValueError("LangChain embedding adapter is deferred.")

        raise ValueError(f"不支持的 capability: {model_config.capability}")

    raise ValueError(f"不支持的 provider: {model_config.provider}")


def get_chat_provider():
    return _build_provider(get_active_model_config(ModelConfig.CAPABILITY_CHAT))


def get_embedding_provider():
    return _build_provider(get_active_model_config(ModelConfig.CAPABILITY_EMBEDDING))


def get_structured_output_provider():
    model_config = get_active_model_config(ModelConfig.CAPABILITY_CHAT)
    if model_config.provider != ModelConfig.PROVIDER_LANGCHAIN:
        raise ValueError(f"不支持 structured output provider: {model_config.provider}")

    return LangChainStructuredOutputProvider(
        endpoint=model_config.endpoint,
        model_name=model_config.model_name,
        options=model_config.options,
    )
