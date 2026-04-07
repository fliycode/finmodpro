from rest_framework import serializers

from llm.models import EvalRecord, ModelConfig


def _mask_api_key(value):
    if not value:
        return ""
    if len(value) <= 10:
        return "*" * len(value)
    return f"{value[:6]}******{value[-4:]}"


class ModelConfigSummarySerializer(serializers.ModelSerializer):
    options = serializers.SerializerMethodField()
    has_api_key = serializers.SerializerMethodField()
    api_key_masked = serializers.SerializerMethodField()

    def get_options(self, obj):
        options = dict(obj.options or {})
        if options.get("api_key"):
            options["api_key"] = _mask_api_key(options["api_key"])
        return options

    def get_has_api_key(self, obj):
        return bool((obj.options or {}).get("api_key"))

    def get_api_key_masked(self, obj):
        return _mask_api_key((obj.options or {}).get("api_key"))

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
            "has_api_key",
            "api_key_masked",
            "is_active",
            "created_at",
            "updated_at",
        )


class ModelConfigActivationSerializer(serializers.Serializer):
    is_active = serializers.BooleanField()


class ModelConfigWriteSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)
    capability = serializers.ChoiceField(choices=ModelConfig.CAPABILITY_CHOICES)
    provider = serializers.ChoiceField(choices=ModelConfig.PROVIDER_CHOICES)
    model_name = serializers.CharField(max_length=255)
    endpoint = serializers.URLField(max_length=500)
    options = serializers.DictField(required=False, default=dict)
    is_active = serializers.BooleanField(required=False, default=False)


class ModelConfigConnectionTestSerializer(serializers.Serializer):
    provider = serializers.ChoiceField(choices=ModelConfig.PROVIDER_CHOICES)
    model_name = serializers.CharField(max_length=255)
    endpoint = serializers.URLField(max_length=500)
    options = serializers.DictField(required=False, default=dict)


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
