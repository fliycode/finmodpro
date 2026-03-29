from rest_framework import serializers

from llm.models import EvalRecord, ModelConfig


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


class PromptConfigUpdateSerializer(serializers.Serializer):
    template = serializers.CharField()


class EvalRecordSummarySerializer(serializers.ModelSerializer):
    model_config_id = serializers.IntegerField(source="model_config.id", allow_null=True)

    class Meta:
        model = EvalRecord
        fields = (
            "id",
            "model_config_id",
            "target_name",
            "task_type",
            "status",
            "qa_accuracy",
            "extraction_accuracy",
            "average_latency_ms",
            "version",
            "metadata",
            "created_at",
        )


class EvalRecordCreateSerializer(serializers.Serializer):
    task_type = serializers.ChoiceField(choices=EvalRecord.TASK_CHOICES)
    model_config_id = serializers.IntegerField(required=False)
    version = serializers.CharField(required=False, allow_blank=True, max_length=128)
