from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("risk", "0005_alter_riskreport_scope_type"),
    ]

    operations = [
        migrations.AlterField(
            model_name="riskextractiontask",
            name="current_step",
            field=models.CharField(
                choices=[
                    ("queued", "Queued"),
                    ("retrieving", "Retrieving"),
                    ("extracting_signals", "Extracting signals"),
                    ("adjudicating", "Adjudicating"),
                    ("routing_review", "Routing review"),
                    ("extracting", "Extracting"),
                    ("verifying", "Verifying"),
                    ("persisting", "Persisting"),
                    ("completed", "Completed"),
                    ("failed", "Failed"),
                ],
                default="queued",
                max_length=32,
            ),
        ),
    ]
