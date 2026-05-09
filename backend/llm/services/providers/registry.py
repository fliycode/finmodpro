from common.exceptions import ProviderConfigurationError
from llm.models import ModelConfig
from llm.services.providers import (
    DashScopeEmbeddingProvider,
    DashScopeRerankProvider,
    DeepSeekChatProvider,
    OllamaChatProvider,
    OllamaEmbeddingProvider,
    OpenAICompatibleChatProvider,
    OpenAICompatibleEmbeddingProvider,
    OpenAICompatibleRerankProvider,
)


PROVIDER_REGISTRY = {
    ModelConfig.PROVIDER_DEEPSEEK: {
        ModelConfig.CAPABILITY_CHAT: DeepSeekChatProvider,
    },
    ModelConfig.PROVIDER_DASHSCOPE: {
        ModelConfig.CAPABILITY_EMBEDDING: DashScopeEmbeddingProvider,
        ModelConfig.CAPABILITY_RERANK: DashScopeRerankProvider,
    },
    ModelConfig.PROVIDER_OLLAMA: {
        ModelConfig.CAPABILITY_CHAT: OllamaChatProvider,
        ModelConfig.CAPABILITY_EMBEDDING: OllamaEmbeddingProvider,
    },
    ModelConfig.PROVIDER_OPENAI_COMPATIBLE: {
        ModelConfig.CAPABILITY_CHAT: OpenAICompatibleChatProvider,
        ModelConfig.CAPABILITY_EMBEDDING: OpenAICompatibleEmbeddingProvider,
        ModelConfig.CAPABILITY_RERANK: OpenAICompatibleRerankProvider,
    },
}


def get_provider_class(*, provider, capability):
    capability_map = PROVIDER_REGISTRY.get(provider, {})
    provider_class = capability_map.get(capability)
    if provider_class is None:
        supported = sorted(capability_map.keys())
        raise ProviderConfigurationError(
            "模型供应商与能力类型不匹配。",
            provider=provider,
            details={
                "capability": capability,
                "supported_capabilities": supported,
            },
        )
    return provider_class
