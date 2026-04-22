from django.db import migrations, models


def seed_dashscope_model_configs(apps, schema_editor):
    ModelConfig = apps.get_model("llm", "ModelConfig")
    ModelConfig.objects.filter(
        capability="embedding",
        provider="ollama",
        is_active=True,
    ).update(is_active=False)

    ModelConfig.objects.bulk_create(
        [
            ModelConfig(
                name="default-dashscope-embedding",
                capability="embedding",
                provider="dashscope",
                model_name="text-embedding-v4",
                endpoint="https://dashscope.aliyuncs.com/compatible-mode/v1",
                options={},
                is_active=True,
            ),
            ModelConfig(
                name="default-dashscope-rerank",
                capability="rerank",
                provider="dashscope",
                model_name="qwen3-vl-rerank",
                endpoint="https://dashscope.aliyuncs.com/api/v1/services/rerank/text-rerank/text-rerank",
                options={},
                is_active=True,
            ),
        ]
    )


def unseed_dashscope_model_configs(apps, schema_editor):
    ModelConfig = apps.get_model("llm", "ModelConfig")
    ModelConfig.objects.filter(
        name__in=["default-dashscope-embedding", "default-dashscope-rerank"],
        provider="dashscope",
    ).delete()
    ModelConfig.objects.filter(
        capability="embedding",
        provider="ollama",
    ).update(is_active=True)


class Migration(migrations.Migration):
    dependencies = [
        ("llm", "0005_finetunerun_artifact_manifest_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="modelconfig",
            name="capability",
            field=models.CharField(
                choices=[
                    ("chat", "Chat"),
                    ("embedding", "Embedding"),
                    ("rerank", "Rerank"),
                ],
                max_length=32,
            ),
        ),
        migrations.AlterField(
            model_name="modelconfig",
            name="provider",
            field=models.CharField(
                choices=[
                    ("ollama", "Ollama"),
                    ("deepseek", "DeepSeek"),
                    ("litellm", "LiteLLM"),
                    ("dashscope", "DashScope"),
                ],
                max_length=32,
            ),
        ),
        migrations.RunPython(
            seed_dashscope_model_configs,
            reverse_code=unseed_dashscope_model_configs,
        ),
    ]
