from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("llm", "0003_alter_modelconfig_provider"),
    ]

    operations = [
        migrations.AlterField(
            model_name="modelconfig",
            name="provider",
            field=models.CharField(
                choices=[
                    ("ollama", "Ollama"),
                    ("deepseek", "DeepSeek"),
                    ("langchain", "LangChain"),
                ],
                max_length=32,
            ),
        ),
    ]
