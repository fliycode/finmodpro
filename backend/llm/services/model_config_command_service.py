"""
模型配置命令服务（类比 SpringBoot 中 @Service 的写操作层）。
负责模型配置的创建、更新、删除、启用状态切换和连接测试。
所有写操作均通过控制器层的权限检查后调用。
"""
from django.db import transaction

from llm.models import ModelConfig
from llm.services.runtime_service import _build_provider


def set_model_config_active_state(*, model_config_id, is_active):
    """切换模型配置的启用/禁用状态。

    使用 select_for_update 行锁确保并发安全。若配置不存在则抛出 ValueError。

    参数:
        model_config_id: int，模型配置的主键 ID。
        is_active: bool，目标启用状态。
    返回:
        ModelConfig 实例，更新后的模型配置。
    异常:
        ValueError: 当指定的模型配置不存在时抛出。
    """
    with transaction.atomic():
        try:
            model_config = ModelConfig.objects.select_for_update().get(id=model_config_id)
        except ModelConfig.DoesNotExist as exc:
            raise ValueError("模型配置不存在。") from exc

        model_config.is_active = is_active
        model_config.save()
        model_config.refresh_from_db()
        return model_config


def create_model_config(*, payload):
    """创建新的模型配置。

    参数:
        payload: dict，包含 ModelConfig 各字段的值（已由序列化器校验）。
    返回:
        ModelConfig 实例，新创建的模型配置。
    """
    model_config = ModelConfig.objects.create(**payload)
    model_config.refresh_from_db()
    return model_config


def update_model_config(*, model_config, payload):
    """更新模型配置。

    特别处理 options 字段：将传入的 options 与现有 options 合并（非覆盖式），
    且若 api_key 字段为空字符串则跳过（保留原有 api_key）。

    参数:
        model_config: ModelConfig 实例，待更新的模型配置。
        payload: dict，包含要更新的字段（已校验）。
    返回:
        ModelConfig 实例，更新后的模型配置。
    """
    incoming_options = payload.pop("options", None)
    for key, value in payload.items():
        setattr(model_config, key, value)
    if incoming_options is not None:
        merged_options = {**(model_config.options or {})}
        for key, value in incoming_options.items():
            if key == "api_key" and not value:
                continue
            merged_options[key] = value
        model_config.options = merged_options
    model_config.save()
    model_config.refresh_from_db()
    return model_config


def delete_model_config(*, model_config):
    """删除模型配置。

    参数:
        model_config: ModelConfig 实例，待删除的模型配置。
    异常:
        ValueError: 当配置处于启用状态时不允许删除。
    """
    if model_config.is_active:
        raise ValueError("启用中的模型配置不能删除。")
    model_config.delete()


def test_model_config_connection(*, payload):
    """测试模型配置的连接是否可达。

    根据能力类型（chat/embedding/rerank）发送最小的测试请求验证端点可用性。
    对于已存在的模型配置（通过 model_config_id 指定），会合并其 options。

    参数:
        payload: dict，包含 provider、model_name、endpoint、options、capability 等信息。
    返回:
        dict，{"ok": True} 表示连接成功。
    异常:
        ValueError: 当指定的 model_config_id 对应的配置不存在时抛出。
        UpstreamServiceError / ServiceConfigurationError: 当连接失败时由 Provider 层抛出。
    """
    payload = dict(payload)
    model_config_id = payload.pop("model_config_id", None)
    existing_model_config = None
    if model_config_id is not None:
        existing_model_config = ModelConfig.objects.filter(id=model_config_id).first()
        if existing_model_config is None:
            raise ValueError("模型配置不存在。")

    merged_options = {
        **((existing_model_config.options if existing_model_config is not None else {}) or {}),
        **(payload.get("options") or {}),
    }
    payload["options"] = merged_options

    provider = _build_provider(ModelConfig(**payload))
    capability = payload["capability"]
    if capability == ModelConfig.CAPABILITY_CHAT:
        provider.chat(messages=[{"role": "user", "content": "ping"}])
    elif capability == ModelConfig.CAPABILITY_EMBEDDING:
        provider.embed(texts=["ping"])
    elif capability == ModelConfig.CAPABILITY_RERANK:
        provider.rerank(query="ping", documents=["ping"], top_n=1)
    return {"ok": True}
