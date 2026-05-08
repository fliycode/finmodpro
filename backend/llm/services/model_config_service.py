from common.exceptions import ModelNotConfiguredError
from llm.models import ModelConfig


def get_manageable_model_configs():
    return ModelConfig.objects.filter(provider=ModelConfig.PROVIDER_LITELLM)


def get_active_model_config(capability):
    active_config = (
        get_manageable_model_configs()
        .filter(capability=capability, is_active=True)
        .order_by("-updated_at", "-id")
        .first()
    )
    if active_config is None:
        raise ModelNotConfiguredError(capability)
    return active_config
