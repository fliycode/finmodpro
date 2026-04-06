from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("llm", "0002_evalrecord"),
    ]

    operations = [
        migrations.AlterField(
            model_name="modelconfig",
            name="provider",
            field=models.CharField(
                choices=[("ollama", "Ollama"), ("deepseek", "DeepSeek")],
                max_length=32,
            ),
        ),
    ]
