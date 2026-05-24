"""
LLM 服务提供商（Provider）包（类比 SpringBoot 中的 SPI/插件接口实现集合）。
该文件将 providers 目录标记为 Python 包，并汇总公开所有具体提供商的实现类。
每个 Provider 封装了与特定 LLM 厂商 API 交互的逻辑，
支持 Chat / Embedding / Rerank 三种能力。
"""
from llm.services.providers.dashscope_provider import DashScopeEmbeddingProvider, DashScopeRerankProvider
from llm.services.providers.deepseek_provider import DeepSeekChatProvider
from llm.services.providers.ollama_provider import OllamaChatProvider, OllamaEmbeddingProvider
from llm.services.providers.openai_compatible_provider import (
    OpenAICompatibleChatProvider,
    OpenAICompatibleEmbeddingProvider,
    OpenAICompatibleRerankProvider,
)

__all__ = [
    "DashScopeEmbeddingProvider",
    "DashScopeRerankProvider",
    "DeepSeekChatProvider",
    "OllamaChatProvider",
    "OllamaEmbeddingProvider",
    "OpenAICompatibleChatProvider",
    "OpenAICompatibleEmbeddingProvider",
    "OpenAICompatibleRerankProvider",
]
