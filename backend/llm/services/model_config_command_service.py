from django.conf import settings
from django.db import transaction

from common.exceptions import ServiceConfigurationError
from llm.models import ModelConfig
from llm.services.litellm_alias_service import sync_litellm_route_for_config, sync_litellm_routes
from llm.services.litellm_route_utils import normalize_upstream_model_name
from llm.services.runtime_service import _build_provider

_LEGACY_LITELLM_OPTION_KEYS = ("api_key", "temperature", "max_tokens")


def _canonical_litellm_route_name(source_model_config):
    name = (source_model_config.name or "").strip()
    if name.startswith("litellm-"):
        return name
    return f"litellm-{name}"


def _build_litellm_route_options(source_model_config):
    if source_model_config.provider == ModelConfig.PROVIDER_LITELLM:
        options = dict(source_model_config.options or {})
        litellm_options = dict(options.get("litellm") or {})
        litellm_options["upstream_model"] = normalize_upstream_model_name(
            provider=litellm_options.get("upstream_provider") or "",
            model_name=litellm_options.get("upstream_model") or source_model_config.model_name,
        )
        options["litellm"] = litellm_options
        return options

    source_options = source_model_config.options or {}
    options = {
        key: source_options[key]
        for key in _LEGACY_LITELLM_OPTION_KEYS
        if source_options.get(key) not in (None, "")
    }
    options["api_base"] = source_model_config.endpoint
    options["litellm"] = {
        "upstream_provider": source_model_config.provider,
        "upstream_model": normalize_upstream_model_name(
            provider=source_model_config.provider,
            model_name=source_model_config.model_name,
        ),
    }
    return options


def ensure_litellm_route_from_model_config(source_model_config):
    route = (
        ModelConfig.objects.filter(
            provider=ModelConfig.PROVIDER_LITELLM,
            capability=source_model_config.capability,
            model_name=source_model_config.model_name,
        )
        .order_by("-is_active", "-updated_at", "-id")
        .first()
    )

    if route is None and source_model_config.provider == ModelConfig.PROVIDER_LITELLM:
        route = source_model_config

    if route is None:
        route = ModelConfig(
            name=_canonical_litellm_route_name(source_model_config),
            capability=source_model_config.capability,
            provider=ModelConfig.PROVIDER_LITELLM,
            model_name=source_model_config.model_name,
        )

    route.endpoint = settings.LITELLM_GATEWAY_URL
    route.description = source_model_config.description
    route.parameter_scale = source_model_config.parameter_scale
    route.options = _build_litellm_route_options(source_model_config)
    route.is_active = True
    route.save()

    if source_model_config.provider != ModelConfig.PROVIDER_LITELLM:
        source_model_config.is_active = False
        source_model_config.save()

    nested_name = f"litellm-{_canonical_litellm_route_name(source_model_config)}"
    ModelConfig.objects.filter(
        provider=ModelConfig.PROVIDER_LITELLM,
        capability=source_model_config.capability,
        name=nested_name,
    ).exclude(id=route.id).delete()

    sync_litellm_route_for_config(route, triggered_by=None)
    route.refresh_from_db()
    return route


def migrate_active_configs_to_litellm(*, triggered_by):
    migrated_capabilities = []
    with transaction.atomic():
        for capability in ModelConfig.CAPABILITY_CHOICES:
            capability_key = capability[0]
            active_source = (
                ModelConfig.objects.filter(capability=capability_key, is_active=True)
                .exclude(provider=ModelConfig.PROVIDER_LITELLM)
                .order_by("-updated_at", "-id")
                .first()
            )
            active_route = (
                ModelConfig.objects.filter(
                    capability=capability_key,
                    provider=ModelConfig.PROVIDER_LITELLM,
                    is_active=True,
                )
                .order_by("-updated_at", "-id")
                .first()
            )
            source_model = active_source or active_route
            if source_model is None:
                raise ServiceConfigurationError(
                    f"未配置启用中的 {capability_key} 模型。",
                    code="model_not_configured",
                )
            ensure_litellm_route_from_model_config(source_model)
            migrated_capabilities.append(capability_key)

        sync_result = sync_litellm_routes(triggered_by=triggered_by)
    return {
        "migrated_capabilities": migrated_capabilities,
        "sync_result": sync_result,
    }


def set_model_config_active_state(*, model_config_id, is_active):
    with transaction.atomic():
        try:
            model_config = ModelConfig.objects.select_for_update().get(id=model_config_id)
        except ModelConfig.DoesNotExist as exc:
            raise ValueError("模型配置不存在。") from exc
        if model_config.provider == ModelConfig.PROVIDER_LITELLM:
            raise ValueError("LiteLLM 遗留配置不能再启用，请先迁移为直连 provider。")

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


def delete_model_config(*, model_config):
    if model_config.is_active:
        raise ValueError("启用中的模型配置不能删除。")
    model_config.delete()


def test_model_config_connection(*, payload):
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
