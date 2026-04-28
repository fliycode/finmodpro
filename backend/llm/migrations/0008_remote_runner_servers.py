import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("llm", "0007_litellm_gateway_audit_models"),
    ]

    operations = [
        migrations.CreateModel(
            name="FineTuneRunnerServer",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=255, unique=True)),
                ("base_url", models.URLField(max_length=500)),
                ("auth_token", models.CharField(blank=True, default="", max_length=255)),
                ("default_work_dir", models.CharField(blank=True, default="", max_length=500)),
                ("is_enabled", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "ordering": ["name", "id"],
            },
        ),
        migrations.AddField(
            model_name="finetunerun",
            name="callback_token_value",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
        migrations.AddField(
            model_name="finetunerun",
            name="runner_server",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="fine_tune_runs",
                to="llm.finetunerunnerserver",
            ),
        ),
    ]
