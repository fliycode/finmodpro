from django.db import migrations


RERANK_ENDPOINT = "https://dashscope.aliyuncs.com/api/v1/services/rerank/text-rerank/text-rerank"


def ensure_active_rerank_model_config(apps, schema_editor):
    ModelConfig = apps.get_model("llm", "ModelConfig")

    existing_rerank_configs = ModelConfig.objects.filter(capability="rerank").order_by("-updated_at", "-id")
    if existing_rerank_configs.exists():
        if not existing_rerank_configs.filter(is_active=True).exists():
            rerank_model = existing_rerank_configs.first()
            rerank_model.is_active = True
            rerank_model.save(update_fields=["is_active", "updated_at"])
        return

    ModelConfig.objects.create(
        name="rerank-active",
        capability="rerank",
        provider="dashscope",
        model_name="qwen3-vl-rerank",
        parameter_scale="",
        endpoint=RERANK_ENDPOINT,
        description="默认重排模型",
        options={},
        is_active=True,
    )


class Migration(migrations.Migration):
    dependencies = [
        ("llm", "0009_modelconfig_parameter_scale_description"),
    ]

    operations = [
        migrations.RunPython(ensure_active_rerank_model_config, migrations.RunPython.noop),
    ]
