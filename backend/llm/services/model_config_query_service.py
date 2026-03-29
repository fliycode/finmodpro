from llm.models import ModelConfig


def list_model_configs():
    return ModelConfig.objects.order_by("capability", "id")
