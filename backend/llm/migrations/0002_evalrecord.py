from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("llm", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="EvalRecord",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("target_name", models.CharField(db_index=True, max_length=255)),
                (
                    "task_type",
                    models.CharField(
                        choices=[("qa", "QA"), ("risk_extraction", "Risk Extraction"), ("report", "Report")],
                        db_index=True,
                        max_length=64,
                    ),
                ),
                ("qa_accuracy", models.DecimalField(blank=True, decimal_places=4, max_digits=5, null=True)),
                ("extraction_accuracy", models.DecimalField(blank=True, decimal_places=4, max_digits=5, null=True)),
                ("average_latency_ms", models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ("version", models.CharField(blank=True, default="", max_length=128)),
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
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "model_config",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=models.SET_NULL,
                        related_name="eval_records",
                        to="llm.modelconfig",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at", "-id"],
            },
        ),
    ]
