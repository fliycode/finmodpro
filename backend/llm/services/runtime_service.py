import os
from urllib.parse import urlparse, urlunparse

from common.exceptions import ProviderConfigurationError
from llm.models import ModelConfig
from llm.services.providers.deepseek_provider import DeepSeekChatProvider
from llm.services.model_config_service import get_active_model_config
from llm.services.providers.litellm_provider import (
    LiteLLMChatProvider,
    LiteLLMEmbeddingProvider,
)
from llm.services.providers.ollama_provider import (
    OllamaChatProvider,
    OllamaEmbeddingProvider,
)


def _normalize_ollama_endpoint(endpoint):
    if not endpoint:
        return endpoint

    parsed = urlparse(endpoint)
    if parsed.scheme not in {"http", "https"}:
        return endpoint

    if os.getenv("APP_ENV") != "production":
        return endpoint

    if parsed.hostname not in {"localhost", "127.0.0.1"}:
        return endpoint

    internal_base = os.getenv("OLLAMA_INTERNAL_URL", "http://ollama:11434").rstrip("/")
    internal_parsed = urlparse(internal_base)
    replacement = parsed._replace(
        scheme=internal_parsed.scheme or parsed.scheme,
        netloc=internal_parsed.netloc or parsed.netloc,
    )
    return urlunparse(replacement)


def _normalize_litellm_endpoint(endpoint):
    if not endpoint:
        return endpoint

    parsed = urlparse(endpoint)
    if parsed.scheme not in {"http", "https"}:
        return endpoint

    if os.getenv("APP_ENV") != "production":
        return endpoint

    if parsed.hostname not in {"localhost", "127.0.0.1"}:
        return endpoint

    internal_base = os.getenv("LITELLM_INTERNAL_URL", "http://litellm:4000").rstrip("/")
    internal_parsed = urlparse(internal_base)
    replacement = parsed._replace(
        scheme=internal_parsed.scheme or parsed.scheme,
        netloc=internal_parsed.netloc or parsed.netloc,
    )
    return urlunparse(replacement)


def _build_provider(model_config):
    if model_config.provider == ModelConfig.PROVIDER_LITELLM:
        if model_config.capability == ModelConfig.CAPABILITY_CHAT:
            return LiteLLMChatProvider(
                endpoint=_normalize_litellm_endpoint(model_config.endpoint),
                model_name=model_config.model_name,
                options=model_config.options,
            )

        if model_config.capability == ModelConfig.CAPABILITY_EMBEDDING:
            return LiteLLMEmbeddingProvider(
                endpoint=_normalize_litellm_endpoint(model_config.endpoint),
                model_name=model_config.model_name,
                options=model_config.options,
            )

        raise ProviderConfigurationError(
            f"Unsupported capability: {model_config.capability}",
            provider=model_config.provider,
            details={"capability": model_config.capability},
        )

    if model_config.provider == ModelConfig.PROVIDER_DEEPSEEK:
        if model_config.capability != ModelConfig.CAPABILITY_CHAT:
            raise ProviderConfigurationError(
                f"Unsupported capability: {model_config.capability}",
                provider=model_config.provider,
                details={
                    "capability": model_config.capability,
                    "supported_capabilities": [ModelConfig.CAPABILITY_CHAT],
                },
            )
        return DeepSeekChatProvider(
            endpoint=model_config.endpoint,
            model_name=model_config.model_name,
            options=model_config.options,
        )

    if model_config.provider != ModelConfig.PROVIDER_OLLAMA:
        raise ProviderConfigurationError(
            f"Unsupported provider: {model_config.provider}",
            provider=model_config.provider,
            details={
                "capability": model_config.capability,
                "supported_providers": [
                    ModelConfig.PROVIDER_OLLAMA,
                    ModelConfig.PROVIDER_DEEPSEEK,
                    ModelConfig.PROVIDER_LITELLM,
                ],
            },
        )

    if model_config.capability == ModelConfig.CAPABILITY_CHAT:
        return OllamaChatProvider(
            endpoint=_normalize_ollama_endpoint(model_config.endpoint),
            model_name=model_config.model_name,
            options=model_config.options,
        )

    if model_config.capability == ModelConfig.CAPABILITY_EMBEDDING:
        return OllamaEmbeddingProvider(
            endpoint=_normalize_ollama_endpoint(model_config.endpoint),
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
