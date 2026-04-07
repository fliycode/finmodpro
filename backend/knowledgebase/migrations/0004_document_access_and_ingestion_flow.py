from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
from django.utils import timezone


def backfill_ingestion_tasks(apps, schema_editor):
    Document = apps.get_model("knowledgebase", "Document")
    IngestionTask = apps.get_model("knowledgebase", "IngestionTask")

    status_mapping = {
        "uploaded": ("queued", "queued"),
        "parsed": ("running", "parsing"),
        "chunked": ("running", "chunking"),
        "indexed": ("succeeded", "completed"),
        "failed": ("failed", "failed"),
    }

    for document in Document.objects.all().iterator():
        if IngestionTask.objects.filter(document_id=document.id).exists():
            continue

        task_status, current_step = status_mapping.get(document.status, ("queued", "queued"))
        started_at = document.updated_at if task_status in {"running", "succeeded", "failed"} else None
        finished_at = document.updated_at if task_status in {"succeeded", "failed"} else None
        IngestionTask.objects.create(
            document_id=document.id,
            status=task_status,
            current_step=current_step,
            error_message=document.error_message if task_status == "failed" else "",
            started_at=started_at,
            finished_at=finished_at,
            created_at=document.created_at or timezone.now(),
            updated_at=document.updated_at or timezone.now(),
        )


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("knowledgebase", "0003_ingestiontask"),
    ]

    operations = [
        migrations.AddField(
            model_name="document",
            name="owner",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="owned_documents",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="document",
            name="uploaded_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="uploaded_documents",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="document",
            name="visibility",
            field=models.CharField(
                choices=[
                    ("private", "Private"),
                    ("internal", "Internal"),
                    ("public", "Public"),
                ],
                default="internal",
                max_length=32,
            ),
        ),
        migrations.AddField(
            model_name="ingestiontask",
            name="current_step",
            field=models.CharField(
                choices=[
                    ("queued", "Queued"),
                    ("parsing", "Parsing"),
                    ("chunking", "Chunking"),
                    ("indexing", "Indexing"),
                    ("completed", "Completed"),
                    ("failed", "Failed"),
                ],
                default="queued",
                max_length=32,
            ),
        ),
        migrations.RunPython(backfill_ingestion_tasks, migrations.RunPython.noop),
    ]
