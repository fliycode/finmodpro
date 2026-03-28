from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("knowledgebase", "0002_documentchunk_vector_id"),
    ]

    operations = [
        migrations.CreateModel(
            name="IngestionTask",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
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
                ("error_message", models.TextField(blank=True)),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("finished_at", models.DateTimeField(blank=True, null=True)),
                ("retry_count", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "document",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="ingestion_tasks",
                        to="knowledgebase.document",
                    ),
                ),
            ],
            options={"ordering": ["id"]},
        ),
    ]
