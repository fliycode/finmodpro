from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("llm", "0003_expand_model_config_for_deepseek"),
    ]

    operations = [
        migrations.AddField(
            model_name="evalrecord",
            name="dataset_name",
            field=models.CharField(blank=True, default="", db_index=True, max_length=255),
        ),
        migrations.AddField(
            model_name="evalrecord",
            name="dataset_version",
            field=models.CharField(blank=True, default="", max_length=128),
        ),
        migrations.AddField(
            model_name="evalrecord",
            name="evaluation_mode",
            field=models.CharField(
                choices=[
                    ("baseline", "Baseline"),
                    ("rag", "RAG"),
                    ("fine_tuned", "Fine-tuned"),
                ],
                db_index=True,
                default="baseline",
                max_length=32,
            ),
        ),
        migrations.AddField(
            model_name="evalrecord",
            name="f1_score",
            field=models.DecimalField(blank=True, decimal_places=4, max_digits=5, null=True),
        ),
        migrations.AddField(
            model_name="evalrecord",
            name="precision",
            field=models.DecimalField(blank=True, decimal_places=4, max_digits=5, null=True),
        ),
        migrations.AddField(
            model_name="evalrecord",
            name="recall",
            field=models.DecimalField(blank=True, decimal_places=4, max_digits=5, null=True),
        ),
        migrations.AddField(
            model_name="evalrecord",
            name="run_notes",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.CreateModel(
            name="FineTuneRun",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "dataset_name",
                    models.CharField(max_length=255),
                ),
                (
                    "dataset_version",
                    models.CharField(blank=True, default="", max_length=128),
                ),
                (
                    "strategy",
                    models.CharField(default="lora", max_length=64),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("running", "Running"),
                            ("succeeded", "Succeeded"),
                            ("failed", "Failed"),
                        ],
                        db_index=True,
                        default="pending",
                        max_length=32,
                    ),
                ),
                (
                    "artifact_path",
                    models.CharField(blank=True, default="", max_length=500),
                ),
                (
                    "metrics",
                    models.JSONField(blank=True, default=dict),
                ),
                (
                    "notes",
                    models.TextField(blank=True, default=""),
                ),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True),
                ),
                (
                    "updated_at",
                    models.DateTimeField(auto_now=True),
                ),
                (
                    "base_model",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="fine_tune_runs",
                        to="llm.modelconfig",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at", "-id"],
            },
        ),
    ]
