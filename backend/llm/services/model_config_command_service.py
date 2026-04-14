from django.db import transaction

from llm.models import ModelConfig
from llm.services.runtime_service import _build_provider


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


def create_model_config(*, payload):
    model_config = ModelConfig.objects.create(**payload)
    model_config.refresh_from_db()
    return model_config


def update_model_config(*, model_config, payload):
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


def test_model_config_connection(*, payload):
    provider = _build_provider(ModelConfig(**payload))
    if payload["capability"] == ModelConfig.CAPABILITY_CHAT:
        provider.chat(messages=[{"role": "user", "content": "ping"}])
    elif payload["capability"] == ModelConfig.CAPABILITY_EMBEDDING:
        provider.embed(texts=["ping"])
    return {"ok": True}
