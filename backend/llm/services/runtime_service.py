from common.exceptions import ProviderConfigurationError
from llm.models import ModelConfig
from llm.services.model_config_service import get_active_model_config
from llm.services.providers.ollama_provider import (
    OllamaChatProvider,
    OllamaEmbeddingProvider,
)


def _build_provider(model_config):
    if model_config.provider != ModelConfig.PROVIDER_OLLAMA:
        raise ProviderConfigurationError(
            f"Unsupported provider: {model_config.provider}",
            provider=model_config.provider,
            details={
                "capability": model_config.capability,
                "supported_providers": [ModelConfig.PROVIDER_OLLAMA],
            },
        )

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

    raise ProviderConfigurationError(
        f"Unsupported capability: {model_config.capability}",
        provider=model_config.provider,
        details={"capability": model_config.capability},
    )


def get_chat_provider():
    return _build_provider(get_active_model_config(ModelConfig.CAPABILITY_CHAT))


def get_embedding_provider():
    return _build_provider(get_active_model_config(ModelConfig.CAPABILITY_EMBEDDING))
