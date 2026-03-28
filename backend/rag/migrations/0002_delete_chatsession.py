from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("rag", "0001_initial"),
    ]

    operations = [
        migrations.DeleteModel(
            name="ChatSession",
        ),
    ]
