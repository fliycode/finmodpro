from rest_framework import serializers

from llm.models import ModelConfig


class ModelConfigSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = ModelConfig
        fields = (
            "id",
            "name",
            "capability",
            "provider",
            "model_name",
            "endpoint",
            "options",
            "is_active",
            "created_at",
            "updated_at",
        )
