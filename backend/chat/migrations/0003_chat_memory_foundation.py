from django.conf import settings
from django.db import migrations, models
from django.db.models import Count, Max, Q
import django.db.models.deletion


def backfill_chat_session_truth(apps, schema_editor):
    ChatSession = apps.get_model("chat", "ChatSession")
    db_alias = schema_editor.connection.alias
    default_title = "新会话"

    sessions = list(
        ChatSession.objects.using(db_alias).annotate(
            backfill_message_count=Count("messages"),
            backfill_last_message_at=Max("messages__created_at"),
        )
    )
    if not sessions:
        return

    for session in sessions:
        session.message_count = session.backfill_message_count or 0
        session.last_message_at = session.backfill_last_message_at
        if session.title and session.title != default_title:
            session.title_status = "ready"
        else:
            session.title_status = "pending"
        session.title_source = "legacy"

    ChatSession.objects.using(db_alias).bulk_update(
        sessions,
        ["message_count", "last_message_at", "title_status", "title_source"],
        batch_size=500,
    )


def noop_reverse(apps, schema_editor):
    return None


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("chat", "0002_chatmessage"),
    ]

    operations = [
        migrations.AddField(
            model_name="chatsession",
            name="last_message_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="chatsession",
            name="message_count",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="chatsession",
            name="rolling_summary",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="chatsession",
            name="summary_updated_through_message_id",
            field=models.PositiveBigIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="chatsession",
            name="title_source",
            field=models.CharField(default="ai", max_length=32),
        ),
        migrations.AddField(
            model_name="chatsession",
            name="title_status",
            field=models.CharField(
                choices=[("pending", "Pending"), ("ready", "Ready"), ("failed", "Failed")],
                default="pending",
                max_length=16,
            ),
        ),
        migrations.AddField(
            model_name="chatmessage",
            name="citations_json",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="chatmessage",
            name="client_message_id",
            field=models.CharField(blank=True, default="", max_length=64),
        ),
        migrations.AddField(
            model_name="chatmessage",
            name="model_metadata_json",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="chatmessage",
            name="status",
            field=models.CharField(
                choices=[
                    ("pending", "Pending"),
                    ("complete", "Complete"),
                    ("failed", "Failed"),
                ],
                default="complete",
                max_length=16,
            ),
        ),
        migrations.CreateModel(
            name="MemoryItem",
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
                    "scope_type",
                    models.CharField(
                        choices=[
                            ("user_global", "User Global"),
                            ("project", "Project"),
                            ("dataset", "Dataset"),
                        ],
                        max_length=32,
                    ),
                ),
                ("scope_key", models.CharField(blank=True, default="", max_length=255)),
                (
                    "memory_type",
                    models.CharField(
                        choices=[
                            ("user_preference", "User Preference"),
                            ("project_background", "Project Background"),
                            ("confirmed_fact", "Confirmed Fact"),
                            ("work_rule", "Work Rule"),
                        ],
                        max_length=32,
                    ),
                ),
                ("title", models.CharField(max_length=255)),
                ("content", models.TextField()),
                (
                    "confidence_score",
                    models.DecimalField(decimal_places=2, default=0.0, max_digits=4),
                ),
                (
                    "source_kind",
                    models.CharField(
                        choices=[("auto", "Auto"), ("manual", "Manual")],
                        default="auto",
                        max_length=16,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("active", "Active"),
                            ("archived", "Archived"),
                            ("deleted", "Deleted"),
                        ],
                        default="active",
                        max_length=16,
                    ),
                ),
                ("pinned", models.BooleanField(default=False)),
                ("fingerprint", models.CharField(blank=True, default="", max_length=255)),
                ("last_verified_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="memory_items",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ["-pinned", "-updated_at", "-id"]},
        ),
        migrations.CreateModel(
            name="MemoryEvidence",
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
                ("evidence_excerpt", models.TextField(blank=True, default="")),
                ("extractor_version", models.CharField(blank=True, default="", max_length=64)),
                (
                    "confirmation_status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("confirmed", "Confirmed"),
                            ("rejected", "Rejected"),
                        ],
                        default="pending",
                        max_length=16,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "memory_item",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="evidence_items",
                        to="chat.memoryitem",
                    ),
                ),
                (
                    "message",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="memory_evidence_items",
                        to="chat.chatmessage",
                    ),
                ),
                (
                    "session",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="memory_evidence_items",
                        to="chat.chatsession",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at", "-id"],
                "constraints": [
                    models.CheckConstraint(
                        condition=Q(session__isnull=False) | Q(message__isnull=False),
                        name="chat_memoryevidence_requires_source",
                    )
                ],
            },
        ),
        migrations.CreateModel(
            name="MemoryActionLog",
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
                    "action",
                    models.CharField(
                        choices=[
                            ("view", "View"),
                            ("delete", "Delete"),
                            ("pin", "Pin"),
                            ("unpin", "Unpin"),
                            ("manual_add", "Manual Add"),
                            ("manual_edit", "Manual Edit"),
                        ],
                        max_length=32,
                    ),
                ),
                ("details_json", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "actor_user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="memory_action_logs",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "memory_item",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="action_logs",
                        to="chat.memoryitem",
                    ),
                ),
            ],
            options={"ordering": ["-created_at", "-id"]},
        ),
        migrations.RunPython(backfill_chat_session_truth, noop_reverse),
    ]
