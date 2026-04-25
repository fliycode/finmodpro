import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("llm", "0006_add_dashscope_provider_and_rerank"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="LiteLLMSyncEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "status",
                    models.CharField(
                        choices=[("success", "Success"), ("failed", "Failed")],
                        max_length=32,
                    ),
                ),
                (
                    "triggered_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                ("message", models.TextField(blank=True, default="")),
                ("checksum", models.CharField(blank=True, default="", max_length=128)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "ordering": ["-created_at", "-id"],
            },
        ),
        migrations.CreateModel(
            name="ModelInvocationLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "model_config",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="invocation_logs",
                        to="llm.modelconfig",
                    ),
                ),
                (
                    "capability",
                    models.CharField(
                        choices=[
                            ("chat", "Chat"),
                            ("embedding", "Embedding"),
                            ("rerank", "Rerank"),
                        ],
                        max_length=32,
                    ),
                ),
                ("provider", models.CharField(choices=[("ollama", "Ollama"), ("deepseek", "DeepSeek"), ("litellm", "LiteLLM"), ("dashscope", "DashScope")], default="litellm", max_length=32)),
                ("alias", models.CharField(max_length=255)),
                ("upstream_model", models.CharField(blank=True, default="", max_length=255)),
                ("stage", models.CharField(blank=True, choices=[("routing", "Routing"), ("fallback", "Fallback"), ("direct", "Direct")], default="", max_length=32)),
                (
                    "status",
                    models.CharField(
                        choices=[("success", "Success"), ("failed", "Failed")],
                        default="success",
                        max_length=32,
                    ),
                ),
                ("latency_ms", models.PositiveIntegerField(default=0)),
                ("request_tokens", models.PositiveIntegerField(default=0)),
                ("response_tokens", models.PositiveIntegerField(default=0)),
                ("error_code", models.CharField(blank=True, default="", max_length=64)),
                ("error_message", models.TextField(blank=True, default="")),
                ("trace_id", models.CharField(blank=True, default="", max_length=128)),
                ("request_id", models.CharField(blank=True, default="", max_length=128)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
            ],
            options={
                "ordering": ["-created_at", "-id"],
            },
        ),
        migrations.AddIndex(
            model_name="modelinvocationlog",
            index=models.Index(fields=["model_config", "-created_at"], name="llm_invoclog_cfg_created_idx"),
        ),
        migrations.AddIndex(
            model_name="modelinvocationlog",
            index=models.Index(fields=["trace_id", "-created_at"], name="llm_invoclog_trace_created_idx"),
        ),
        migrations.AddIndex(
            model_name="modelinvocationlog",
            index=models.Index(fields=["request_id", "-created_at"], name="llm_invoclog_reqid_created_idx"),
        ),
    ]
