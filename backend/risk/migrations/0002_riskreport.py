from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("risk", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="RiskReport",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "scope_type",
                    models.CharField(
                        choices=[("company", "Company"), ("time_range", "Time Range")],
                        db_index=True,
                        max_length=32,
                    ),
                ),
                ("title", models.CharField(max_length=255)),
                ("company_name", models.CharField(blank=True, db_index=True, max_length=255, null=True)),
                ("period_start", models.DateField(blank=True, db_index=True, null=True)),
                ("period_end", models.DateField(blank=True, db_index=True, null=True)),
                ("summary", models.TextField(blank=True)),
                ("content", models.TextField()),
                ("source_metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "ordering": ["-created_at", "-id"],
            },
        ),
    ]
