from django.db import transaction

from llm.models import ModelConfig
from llm.services.litellm_alias_service import ensure_litellm_route_from_model_config, sync_litellm_routes
from llm.services.model_config_service import get_active_model_config
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


def migrate_active_configs_to_litellm(*, triggered_by):
    """For each active chat/embedding config, ensure a LiteLLM route exists and is active."""
    migrated = []
    with transaction.atomic():
        for capability in (ModelConfig.CAPABILITY_CHAT, ModelConfig.CAPABILITY_EMBEDDING):
            active = get_active_model_config(capability)
            route = ensure_litellm_route_from_model_config(active)
            route.is_active = True
            route.save(update_fields=["is_active", "updated_at"])
            migrated.append(capability)
    sync_result = sync_litellm_routes(triggered_by=triggered_by)
    return {"migrated_capabilities": migrated, "sync_result": sync_result}
