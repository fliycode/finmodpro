from pathlib import Path

from django.conf import settings


def _build_litellm_alias_config(*, alias, upstream_model_name, api_base):
    return (
        "model_list:\n"
        f"  - model_name: {alias}\n"
        "    litellm_params:\n"
        f"      model: openai/{upstream_model_name}\n"
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
