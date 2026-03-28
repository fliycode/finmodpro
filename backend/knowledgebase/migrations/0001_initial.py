from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Document",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=255)),
                ("file", models.FileField(upload_to="knowledgebase/documents/")),
                ("filename", models.CharField(max_length=255)),
                ("doc_type", models.CharField(max_length=32)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("uploaded", "Uploaded"),
                            ("parsed", "Parsed"),
                            ("chunked", "Chunked"),
                            ("indexed", "Indexed"),
                            ("failed", "Failed"),
                        ],
                        default="uploaded",
                        max_length=32,
                    ),
                ),
                ("source_date", models.DateField(blank=True, null=True)),
                ("parsed_text", models.TextField(blank=True)),
                ("error_message", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["id"]},
        ),
        migrations.CreateModel(
            name="DocumentChunk",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("chunk_index", models.PositiveIntegerField()),
                ("content", models.TextField()),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "document",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="chunks",
                        to="knowledgebase.document",
                    ),
                ),
            ],
            options={
                "ordering": ["chunk_index"],
                "unique_together": {("document", "chunk_index")},
            },
        ),
    ]
