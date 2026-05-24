"""
模型配置基础服务（类比 SpringBoot 中 @Service 的通用查询层）。
提供"可管理的模型配置"的定义（排除 LiteLLM 旧版供应商）和按能力类型获取当前活跃配置的方法。
"""
from common.exceptions import ModelNotConfiguredError
from llm.models import ModelConfig


def get_manageable_model_configs():
    """获取所有可管理的模型配置（排除 LiteLLM 旧版供应商）。

    返回:
        QuerySet，包含除 LiteLLM 外的所有 ModelConfig 记录。
    """
    return ModelConfig.objects.exclude(provider=ModelConfig.PROVIDER_LITELLM)


def get_active_model_config(capability):
    """获取指定能力类型下当前启用的模型配置。

    参数:
        capability: str，能力类型（'chat' / 'embedding' / 'rerank'）。
    返回:
        ModelConfig 实例，当前启用的模型配置。
    异常:
        ModelNotConfiguredError: 当没有启用任何该能力的模型配置时抛出。
    """
    active_config = (
        get_manageable_model_configs()
        .filter(capability=capability, is_active=True)
        .order_by("-updated_at", "-id")
        .first()
    )
    if active_config is None:
        raise ModelNotConfiguredError(capability)
    return active_config
