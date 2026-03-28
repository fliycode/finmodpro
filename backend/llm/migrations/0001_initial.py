from django.db import migrations, models


def seed_default_model_configs(apps, schema_editor):
    ModelConfig = apps.get_model("llm", "ModelConfig")
    ModelConfig.objects.bulk_create(
        [
            ModelConfig(
                name="default-chat",
                capability="chat",
                provider="ollama",
                model_name="llama3.2",
                endpoint="http://localhost:11434",
                options={},
                is_active=True,
            ),
            ModelConfig(
                name="default-embedding",
                capability="embedding",
                provider="ollama",
                model_name="mxbai-embed-large",
                endpoint="http://localhost:11434",
                options={},
                is_active=True,
            ),
        ]
    )


def unseed_default_model_configs(apps, schema_editor):
    ModelConfig = apps.get_model("llm", "ModelConfig")
    ModelConfig.objects.filter(
        name__in=["default-chat", "default-embedding"],
        provider="ollama",
    ).delete()


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="ModelConfig",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=255)),
                ("capability", models.CharField(choices=[("chat", "Chat"), ("embedding", "Embedding")], max_length=32)),
                ("provider", models.CharField(choices=[("ollama", "Ollama")], max_length=32)),
                ("model_name", models.CharField(max_length=255)),
                ("endpoint", models.URLField(max_length=500)),
                ("options", models.JSONField(blank=True, default=dict)),
                ("is_active", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "ordering": ["capability", "id"],
                "unique_together": {("capability", "name")},
            },
        ),
        migrations.RunPython(seed_default_model_configs, unseed_default_model_configs),
    ]
