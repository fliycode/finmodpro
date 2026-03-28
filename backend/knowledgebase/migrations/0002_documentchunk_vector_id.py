from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("knowledgebase", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="documentchunk",
            name="vector_id",
            field=models.CharField(blank=True, db_index=True, max_length=64),
        ),
    ]
