from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("llm", "0008_remote_runner_servers"),
    ]

    operations = [
        migrations.AddField(
            model_name="modelconfig",
            name="description",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="modelconfig",
            name="parameter_scale",
            field=models.CharField(blank=True, default="", max_length=64),
        ),
    ]
