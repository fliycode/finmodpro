from django.db import transaction

from llm.models import ModelConfig


def set_model_config_active_state(*, model_config_id, is_active):
    with transaction.atomic():
        try:
            model_config = ModelConfig.objects.select_for_update().get(id=model_config_id)
        except ModelConfig.DoesNotExist as exc:
            raise ValueError("模型配置不存在。") from exc

        model_config.is_active = is_active
        model_config.save()
        model_config.refresh_from_db()
        return model_config
