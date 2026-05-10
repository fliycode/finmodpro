from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("chat", "0003_chat_memory_foundation"),
    ]

    operations = [
        migrations.AddField(
            model_name="memoryitem",
            name="embedding",
            field=models.JSONField(blank=True, default=list),
        ),
    ]
