from django.conf import settings
from django.db import transaction

from llm.models import ModelConfig
from llm.services.litellm_alias_service import sync_litellm_routes
from llm.services.model_config_service import get_active_model_config
from llm.services.runtime_service import _build_provider


def _strip_litellm_prefixes(name):
    normalized = name or ""
    while normalized.startswith("litellm-"):
        normalized = normalized.removeprefix("litellm-")
    return normalized


def _build_upstream_model_name(*, provider, model_name):
    if not model_name:
        return ""
    if "/" in model_name:
        return model_name
    prefix = provider or "openai"
    return f"{prefix}/{model_name}"


def _build_litellm_route_options(model_config):
    source_options = dict(model_config.options or {})
    litellm_options = dict(source_options.get("litellm") or {})

    if model_config.provider == ModelConfig.PROVIDER_LITELLM:
        upstream_provider = litellm_options.get("upstream_provider") or ""
        upstream_model = litellm_options.get("upstream_model") or _build_upstream_model_name(
            provider=upstream_provider or "openai",
            model_name=model_config.model_name,
        )
        api_base = source_options.get("api_base") or litellm_options.get("base_url") or model_config.endpoint
    else:
        upstream_provider = litellm_options.get("upstream_provider") or model_config.provider
        upstream_model = litellm_options.get("upstream_model") or _build_upstream_model_name(
            provider=upstream_provider,
            model_name=model_config.model_name,
        )
        api_base = source_options.get("api_base") or model_config.endpoint

    litellm_options["upstream_provider"] = upstream_provider
    litellm_options["upstream_model"] = upstream_model
    litellm_options["base_url"] = api_base
    source_options["api_base"] = api_base
    source_options["litellm"] = litellm_options
    return source_options


def _litellm_route_has_required_metadata(model_config):
    options = model_config.options or {}
    litellm_options = options.get("litellm") or {}
    return bool(
        options.get("api_key")
        and options.get("api_base")
        and litellm_options.get("upstream_provider")
        and litellm_options.get("upstream_model")
    )


def _find_original_source_model_config(model_config):
    base_name = _strip_litellm_prefixes(model_config.name)
    candidates = ModelConfig.objects.filter(capability=model_config.capability).exclude(
        provider=ModelConfig.PROVIDER_LITELLM
    )
    source = candidates.filter(name=base_name).order_by("-id").first()
    if source is not None:
        return source
    return candidates.filter(model_name=model_config.model_name).order_by("-is_active", "-id").first()


def _resolve_migration_source_model_config(model_config):
    if model_config.provider != ModelConfig.PROVIDER_LITELLM:
        return model_config

    if model_config.name.startswith("litellm-litellm-") or not _litellm_route_has_required_metadata(model_config):
        source = _find_original_source_model_config(model_config)
        if source is not None:
            return source
    return model_config


def ensure_litellm_route_from_model_config(model_config):
    """Get or create a LiteLLM ModelConfig route for the given model config."""
    source_model_config = _resolve_migration_source_model_config(model_config)

    if source_model_config.provider == ModelConfig.PROVIDER_LITELLM:
        route = source_model_config
    else:
        litellm_name = f"litellm-{_strip_litellm_prefixes(source_model_config.name)}"
        route, _ = ModelConfig.objects.get_or_create(
            capability=source_model_config.capability,
            name=litellm_name,
            defaults={
                "provider": ModelConfig.PROVIDER_LITELLM,
                "model_name": source_model_config.model_name,
                "endpoint": settings.LITELLM_GATEWAY_URL,
                "options": {},
                "is_active": False,
            },
        )

    route.provider = ModelConfig.PROVIDER_LITELLM
    route.model_name = source_model_config.model_name
    route.endpoint = settings.LITELLM_GATEWAY_URL
    route.options = _build_litellm_route_options(source_model_config)
    route.save()
    route.refresh_from_db()
    return route


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
