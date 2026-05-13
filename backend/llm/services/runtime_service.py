from contextlib import contextmanager
from contextvars import ContextVar

from common.exceptions import ProviderConfigurationError
from llm.models import ModelConfig
from llm.services.model_config_service import get_active_model_config
from llm.services.providers.registry import get_provider_class

_PROVIDER_RUNTIME_OPTIONS = ContextVar("provider_runtime_options", default=None)


@contextmanager
def provider_runtime_options(options=None):
    token = _PROVIDER_RUNTIME_OPTIONS.set(options or None)
    try:
        yield
    finally:
        _PROVIDER_RUNTIME_OPTIONS.reset(token)


def _build_provider(model_config):
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
    model_config = get_active_model_config(ModelConfig.CAPABILITY_CHAT)
    if model_config.capability != ModelConfig.CAPABILITY_CHAT:
        raise ProviderConfigurationError(
            "当前启用模型不支持对话能力。",
            provider=model_config.provider,
            details={"capability": model_config.capability},
        )
    return _build_provider(model_config)


def get_embedding_provider():
    model_config = get_active_model_config(ModelConfig.CAPABILITY_EMBEDDING)
    return _build_provider(model_config)


def get_rerank_provider():
    model_config = get_active_model_config(ModelConfig.CAPABILITY_RERANK)
    return _build_provider(model_config)
