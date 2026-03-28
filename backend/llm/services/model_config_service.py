from llm.models import ModelConfig


def get_active_model_config(capability):
    active_config = (
        ModelConfig.objects.filter(capability=capability, is_active=True)
        .order_by("-updated_at", "-id")
        .first()
    )
    if active_config is None:
        raise ValueError(f"未配置启用中的 {capability} 模型。")
    return active_config
