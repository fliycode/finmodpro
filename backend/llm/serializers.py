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


class ModelConfigActivationSerializer(serializers.Serializer):
    is_active = serializers.BooleanField()


class PromptConfigSummarySerializer(serializers.Serializer):
    key = serializers.CharField()
    category = serializers.CharField()
    name = serializers.CharField()
    template = serializers.CharField()
    variables = serializers.ListField(child=serializers.CharField())
    updated_at = serializers.DateTimeField()
