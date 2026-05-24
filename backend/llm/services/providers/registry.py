"""
Provider 注册表（类比 SpringBoot 中的 Bean 注册/工厂模式）。

该文件维护一个字典结构的路由表：PROVIDER_REGISTRY，
将 (供应商, 能力类型) 元组映射到具体的 Provider 实现类。

当运行时需要创建 Provider 时，通过 get_provider_class() 查找对应的类，
若找不到匹配项则抛出 ProviderConfigurationError。
"""
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


# 供应商-能力映射表
# 结构：{ provider: { capability: ProviderClass } }
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
    """根据供应商名称和能力类型查找对应的 Provider 实现类。

    参数:
        provider: str，供应商名称（如 'deepseek'、'dashscope'）。
        capability: str，能力类型（'chat'、'embedding'、'rerank'）。

    返回:
        type，Provider 实现类（BaseChatProvider / BaseEmbeddingProvider / BaseRerankProvider 的子类）。

    异常:
        ProviderConfigurationError: 当供应商不支持该能力类型时抛出，
                                    错误详情中包含该供应商支持的 capability 列表。
    """
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
