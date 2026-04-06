from llm.models import ModelConfig


def list_model_configs():
    return ModelConfig.objects.order_by("capability", "id")


def get_model_config(*, model_config_id):
    return ModelConfig.objects.filter(id=model_config_id).first()
