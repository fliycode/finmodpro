import django.core.validators
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("knowledgebase", "0003_ingestiontask"),
    ]

    operations = [
        migrations.CreateModel(
            name="RiskEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("company_name", models.CharField(db_index=True, max_length=255)),
                ("risk_type", models.CharField(db_index=True, max_length=128)),
                (
                    "risk_level",
                    models.CharField(
                        choices=[("low", "Low"), ("medium", "Medium"), ("high", "High"), ("critical", "Critical")],
                        db_index=True,
                        default="medium",
                        max_length=32,
                    ),
                ),
                ("event_time", models.DateTimeField(blank=True, db_index=True, null=True)),
                ("summary", models.TextField()),
                ("evidence_text", models.TextField()),
                (
                    "confidence_score",
                    models.DecimalField(
                        decimal_places=3,
                        max_digits=4,
                        validators=[
                            django.core.validators.MinValueValidator(0),
                            django.core.validators.MaxValueValidator(1),
                        ],
                    ),
                ),
                (
                    "review_status",
                    models.CharField(
                        choices=[("pending", "Pending"), ("approved", "Approved"), ("rejected", "Rejected")],
                        db_index=True,
                        default="pending",
                        max_length=32,
                    ),
                ),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "chunk",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="risk_events",
                        to="knowledgebase.documentchunk",
                    ),
                ),
                (
                    "document",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="risk_events",
                        to="knowledgebase.document",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at", "-id"],
            },
        ),
    ]
