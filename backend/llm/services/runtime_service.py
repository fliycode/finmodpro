"""
运行时服务（类比 SpringBoot 中 @Service 的 Provider 工厂层）。
负责根据模型配置动态构建对应的 LLM Provider 实例。
通过 ContextVar 机制支持请求级别的 Provider 运行时选项覆盖（如超时等参数）。
"""
from contextlib import contextmanager
from contextvars import ContextVar

from common.exceptions import ProviderConfigurationError
from llm.models import ModelConfig
from llm.services.model_config_service import get_active_model_config
from llm.services.providers.registry import get_provider_class

# 线程/协程安全的上下文变量，存储当前请求级别的 Provider 运行时选项
_PROVIDER_RUNTIME_OPTIONS = ContextVar("provider_runtime_options", default=None)


@contextmanager
def provider_runtime_options(options=None):
    """上下文管理器，用于临时设置 Provider 的运行时选项。

    在 with 块内，所有通过 _build_provider 创建的 Provider 都会合并这些选项。
    典型用法：在 API 请求处理中设置自定义超时等参数。

    参数:
        options: dict 或 None，要合并的运行时选项。
    """
    token = _PROVIDER_RUNTIME_OPTIONS.set(options or None)
    try:
        yield
    finally:
        _PROVIDER_RUNTIME_OPTIONS.reset(token)


def _build_provider(model_config):
    """根据模型配置构建对应的 Provider 实例。

    从注册表中查找 provider + capability 对应的 Provider 类并实例化。
    实例化时合并 model_config.options 和当前 ContextVar 中的运行时选项。

    参数:
        model_config: ModelConfig 实例，包含 provider、capability、endpoint 等信息。
    返回:
        BaseChatProvider / BaseEmbeddingProvider / BaseRerankProvider 的实例。
    异常:
        ProviderConfigurationError: 当供应商与能力类型不匹配时抛出。
    """
    runtime_options = _PROVIDER_RUNTIME_OPTIONS.get()
    provider_class = get_provider_class(
        provider=model_config.provider,
        capability=model_config.capability,
    )
    return provider_class(
        endpoint=model_config.endpoint,
        model_name=model_config.model_name,
        options={**(model_config.options or {}), **(runtime_options or {})},
        model_config=model_config if model_config.pk else None,
    )


def get_chat_provider():
    """获取当前启用的 Chat（对话）Provider。

    返回:
        BaseChatProvider 实例。
    异常:
        ProviderConfigurationError: 当前启用的模型不支持对话能力。
    """
    model_config = get_active_model_config(ModelConfig.CAPABILITY_CHAT)
    if model_config.capability != ModelConfig.CAPABILITY_CHAT:
        raise ProviderConfigurationError(
            "当前启用模型不支持对话能力。",
            provider=model_config.provider,
            details={"capability": model_config.capability},
        )
    return _build_provider(model_config)


def get_embedding_provider():
    """获取当前启用的 Embedding（向量嵌入）Provider。

    返回:
        BaseEmbeddingProvider 实例。
    """
    model_config = get_active_model_config(ModelConfig.CAPABILITY_EMBEDDING)
    return _build_provider(model_config)


def get_rerank_provider():
    """获取当前启用的 Rerank（重排序）Provider。

    返回:
        BaseRerankProvider 实例。
    """
    model_config = get_active_model_config(ModelConfig.CAPABILITY_RERANK)
    return _build_provider(model_config)
