from django.db import migrations


LITELLM_PROVIDER = "litellm"
CAPABILITIES = ("chat", "embedding", "rerank")


def _strip_upstream_prefix(model_name):
    value = (model_name or "").strip()
    if "/" not in value:
        return value
    return value.split("/", 1)[1].strip()


def _restored_name(route_name, capability):
    value = (route_name or "").strip()
    if value.startswith("litellm-"):
        value = value[len("litellm-") :]
    return value or f"{capability}-restored"


def restore_direct_provider_actives(apps, schema_editor):
    ModelConfig = apps.get_model("llm", "ModelConfig")

    for capability in CAPABILITIES:
        if ModelConfig.objects.exclude(provider=LITELLM_PROVIDER).filter(
            capability=capability,
            is_active=True,
        ).exists():
            continue

        legacy_route = (
            ModelConfig.objects.filter(
                provider=LITELLM_PROVIDER,
                capability=capability,
                is_active=True,
            )
            .order_by("-updated_at", "-id")
            .first()
        )
        if legacy_route is None:
            continue

        route_options = dict(legacy_route.options or {})
        litellm_options = dict(route_options.get("litellm") or {})
        provider = (litellm_options.get("upstream_provider") or "").strip() or "openai_compatible"
        upstream_model = litellm_options.get("upstream_model") or legacy_route.model_name
        model_name = _strip_upstream_prefix(upstream_model) or legacy_route.model_name
        endpoint = (
            route_options.get("api_base")
            or litellm_options.get("base_url")
            or legacy_route.endpoint
        )

        direct_config = (
            ModelConfig.objects.exclude(provider=LITELLM_PROVIDER)
            .filter(
                capability=capability,
                provider=provider,
                model_name=model_name,
            )
            .order_by("-updated_at", "-id")
            .first()
        )

        if direct_config is None:
            base_name = _restored_name(legacy_route.name, capability)
            candidate_name = base_name
            suffix = 2
            while ModelConfig.objects.filter(
                capability=capability,
                name=candidate_name,
            ).exists():
                candidate_name = f"{base_name}-{suffix}"
                suffix += 1
            direct_config = ModelConfig.objects.create(
                name=candidate_name,
                capability=capability,
                provider=provider,
                model_name=model_name,
                endpoint=endpoint,
                description=legacy_route.description,
                parameter_scale=legacy_route.parameter_scale,
                options={},
                is_active=False,
            )

        merged_options = dict(direct_config.options or {})
        if route_options.get("api_key") and not merged_options.get("api_key"):
            merged_options["api_key"] = route_options["api_key"]
        for key in ("temperature", "max_tokens"):
            if route_options.get(key) is not None and key not in merged_options:
                merged_options[key] = route_options[key]

        direct_config.endpoint = endpoint or direct_config.endpoint
        if not direct_config.description:
            direct_config.description = legacy_route.description
        if not direct_config.parameter_scale:
            direct_config.parameter_scale = legacy_route.parameter_scale
        direct_config.options = merged_options
        direct_config.is_active = True
        direct_config.save(update_fields=["endpoint", "description", "parameter_scale", "options", "is_active"])

        ModelConfig.objects.filter(capability=capability).exclude(id=direct_config.id).update(
            is_active=False
        )


class Migration(migrations.Migration):
    dependencies = [
        ("llm", "0011_modelconfig_input_price_per_million_and_more"),
    ]

    operations = [
        migrations.RunPython(restore_direct_provider_actives, migrations.RunPython.noop),
    ]
