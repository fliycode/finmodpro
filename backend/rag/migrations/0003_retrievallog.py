from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("rag", "0002_delete_chatsession"),
    ]

    operations = [
        migrations.RenameModel(
            old_name="RetrievalAuditLog",
            new_name="RetrievalLog",
        ),
        migrations.AddField(
            model_name="retrievallog",
            name="duration_ms",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="retrievallog",
            name="metadata",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="retrievallog",
            name="source",
            field=models.CharField(
                choices=[
                    ("retrieval_api", "Retrieval API"),
                    ("chat_ask", "Chat Ask"),
                ],
                default="retrieval_api",
                max_length=32,
            ),
        ),
        migrations.AddField(
            model_name="retrievallog",
            name="top_k",
            field=models.PositiveIntegerField(default=5),
        ),
        migrations.AlterModelOptions(
            name="retrievallog",
            options={"ordering": ["-created_at", "-id"]},
        ),
    ]
