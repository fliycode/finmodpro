import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("knowledgebase", "0011_add_file_hash_to_document"),
        ("risk", "0002_riskreport"),
    ]

    operations = [
        migrations.CreateModel(
            name="RiskExtractionTask",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("celery_task_id", models.CharField(blank=True, db_index=True, max_length=255)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("queued", "Queued"),
                            ("running", "Running"),
                            ("succeeded", "Succeeded"),
                            ("failed", "Failed"),
                        ],
                        default="queued",
                        max_length=32,
                    ),
                ),
                (
                    "current_step",
                    models.CharField(
                        choices=[
                            ("queued", "Queued"),
                            ("extracting", "Extracting"),
                            ("completed", "Completed"),
                            ("failed", "Failed"),
                        ],
                        default="queued",
                        max_length=32,
                    ),
                ),
                ("progress", models.PositiveSmallIntegerField(default=6)),
                ("created_count", models.PositiveIntegerField(default=0)),
                ("message", models.TextField(blank=True)),
                ("error_message", models.TextField(blank=True)),
                ("result_payload", models.JSONField(blank=True, default=dict)),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("finished_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "document",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="risk_extraction_tasks",
                        to="knowledgebase.document",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at", "-updated_at"],
            },
        ),
    ]
