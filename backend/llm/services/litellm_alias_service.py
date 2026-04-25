from pathlib import Path

from django.conf import settings

from llm.models import LiteLLMSyncEvent, ModelConfig
from llm.services.litellm_config_render_service import try_build_rendered_litellm_config


def _build_litellm_alias_config(*, alias, upstream_model_name, api_base):
    if "/" not in upstream_model_name:
        upstream_model_name = f"openai/{upstream_model_name}"
    return (
        "model_list:\n"
        f"  - model_name: {alias}\n"
        "    litellm_params:\n"
        f"      model: {upstream_model_name}\n"
        f"      api_base: {api_base}\n"
    )


def provision_litellm_alias(*, fine_tune_run):
    alias = fine_tune_run.deployment_model_name.strip()
    api_base = fine_tune_run.deployment_endpoint.strip()
    if not alias or not api_base:
        return None

    generated_root = Path(settings.LITELLM_GENERATED_CONFIG_ROOT)
    generated_root.mkdir(parents=True, exist_ok=True)
    config_path = generated_root / f"{fine_tune_run.run_key}.yaml"
    config_path.write_text(
        _build_litellm_alias_config(
            alias=alias,
            upstream_model_name=alias,
            api_base=api_base,
        ),
        encoding="utf-8",
    )
    return {
        "litellm_alias": alias,
        "litellm_config_path": str(config_path),
    }


def sync_litellm_route_for_config(model_config, *, triggered_by):
    """Write a YAML snippet for a single model config and record a sync event."""
    generated_root = Path(settings.LITELLM_GENERATED_CONFIG_ROOT)
    try:
        generated_root.mkdir(parents=True, exist_ok=True)
        route_key = f"route-{model_config.capability}-{model_config.id}"
        config_path = generated_root / f"{route_key}.yaml"
        api_base = (model_config.options or {}).get("api_base") or model_config.endpoint
        upstream_model_name = (
            (model_config.options or {}).get("litellm", {}).get("upstream_model")
            or model_config.model_name
        )
        config_path.write_text(
            _build_litellm_alias_config(
                alias=model_config.model_name,
                upstream_model_name=upstream_model_name,
                api_base=api_base,
            ),
            encoding="utf-8",
        )
        status = LiteLLMSyncEvent.STATUS_SUCCESS
        message = f"Synced model config {model_config.id} ({model_config.name})."
    except Exception as exc:  # pragma: no cover
        status = LiteLLMSyncEvent.STATUS_FAILED
        message = str(exc)

    event = LiteLLMSyncEvent.objects.create(
        status=status,
        triggered_by=triggered_by,
        message=message,
    )
    if status == LiteLLMSyncEvent.STATUS_SUCCESS:
        try_build_rendered_litellm_config(
            base_config_path=settings.LITELLM_BASE_CONFIG_PATH,
            generated_root=str(settings.LITELLM_GENERATED_CONFIG_ROOT),
            output_path=settings.LITELLM_RENDERED_CONFIG_PATH,
        )
    return {"status": status, "sync_event_id": event.id, "route_count": 1}


def sync_litellm_routes(*, triggered_by):
    """Write YAML snippets for all active LiteLLM routes and record a sync event."""
    active_routes = list(
        ModelConfig.objects.filter(provider=ModelConfig.PROVIDER_LITELLM, is_active=True)
    )
    generated_root = Path(settings.LITELLM_GENERATED_CONFIG_ROOT)
    try:
        generated_root.mkdir(parents=True, exist_ok=True)
        for route in active_routes:
            route_key = f"route-{route.capability}-{route.id}"
            config_path = generated_root / f"{route_key}.yaml"
            api_base = (route.options or {}).get("api_base") or route.endpoint
            upstream_model_name = (
                (route.options or {}).get("litellm", {}).get("upstream_model")
                or route.model_name
            )
            config_path.write_text(
                _build_litellm_alias_config(
                    alias=route.model_name,
                    upstream_model_name=upstream_model_name,
                    api_base=api_base,
                ),
                encoding="utf-8",
            )
        status = LiteLLMSyncEvent.STATUS_SUCCESS
        message = f"Synced {len(active_routes)} active LiteLLM route(s)."
    except Exception as exc:  # pragma: no cover
        status = LiteLLMSyncEvent.STATUS_FAILED
        message = str(exc)

    event = LiteLLMSyncEvent.objects.create(
        status=status,
        triggered_by=triggered_by,
        message=message,
    )
    if status == LiteLLMSyncEvent.STATUS_SUCCESS:
        try_build_rendered_litellm_config(
            base_config_path=settings.LITELLM_BASE_CONFIG_PATH,
            generated_root=str(settings.LITELLM_GENERATED_CONFIG_ROOT),
            output_path=settings.LITELLM_RENDERED_CONFIG_PATH,
        )
    return {"status": status, "sync_event_id": event.id, "route_count": len(active_routes)}
