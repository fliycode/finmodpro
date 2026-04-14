from rest_framework import serializers

from llm.models import EvalRecord, FineTuneRun, ModelConfig


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
    fine_tune_run_count = serializers.SerializerMethodField()
    latest_fine_tune_dataset = serializers.SerializerMethodField()
    latest_fine_tune_status = serializers.SerializerMethodField()
    latest_fine_tune_artifact_path = serializers.SerializerMethodField()

    def get_options(self, obj):
        options = dict(obj.options or {})
        if options.get("api_key"):
            options["api_key"] = _mask_api_key(options["api_key"])
        return options

    def get_has_api_key(self, obj):
        return bool((obj.options or {}).get("api_key"))

    def get_api_key_masked(self, obj):
        return _mask_api_key((obj.options or {}).get("api_key"))

    def _get_latest_fine_tune_run(self, obj):
        runs = getattr(obj, "fine_tune_runs", None)
        if runs is None:
            return None
        if hasattr(runs, "all"):
            return runs.all().order_by("-created_at", "-id").first()
        return None

    def get_fine_tune_run_count(self, obj):
        runs = getattr(obj, "fine_tune_runs", None)
        if runs is None or not hasattr(runs, "count"):
            return 0
        return runs.count()

    def get_latest_fine_tune_dataset(self, obj):
        latest_run = self._get_latest_fine_tune_run(obj)
        return latest_run.dataset_name if latest_run else ""

    def get_latest_fine_tune_status(self, obj):
        latest_run = self._get_latest_fine_tune_run(obj)
        return latest_run.status if latest_run else ""

    def get_latest_fine_tune_artifact_path(self, obj):
        latest_run = self._get_latest_fine_tune_run(obj)
        return latest_run.artifact_path if latest_run else ""

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
            "fine_tune_run_count",
            "latest_fine_tune_dataset",
            "latest_fine_tune_status",
            "latest_fine_tune_artifact_path",
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
            "evaluation_mode",
            "target_name",
            "task_type",
            "status",
            "qa_accuracy",
            "extraction_accuracy",
            "precision",
            "recall",
            "f1_score",
            "average_latency_ms",
            "version",
            "dataset_name",
            "dataset_version",
            "run_notes",
            "metadata",
            "created_at",
        )


class EvalRecordCreateSerializer(serializers.Serializer):
    task_type = serializers.ChoiceField(choices=EvalRecord.TASK_CHOICES)
    model_config_id = serializers.IntegerField(required=False)
    version = serializers.CharField(required=False, allow_blank=True, max_length=128)
    evaluation_mode = serializers.ChoiceField(choices=EvalRecord.EVALUATION_MODE_CHOICES, required=False, default=EvalRecord.EVALUATION_MODE_BASELINE)
    dataset_name = serializers.CharField(required=False, allow_blank=True, max_length=255, default="")
    dataset_version = serializers.CharField(required=False, allow_blank=True, max_length=128, default="")
    run_notes = serializers.CharField(required=False, allow_blank=True, default="")


class FineTuneRunSummarySerializer(serializers.ModelSerializer):
    base_model_id = serializers.IntegerField(source="base_model.id")
    base_model_name = serializers.CharField(source="base_model.name")
    base_model_capability = serializers.CharField(source="base_model.capability")
    base_model_provider = serializers.CharField(source="base_model.provider")

    class Meta:
        model = FineTuneRun
        fields = (
            "id",
            "base_model_id",
            "base_model_name",
            "base_model_capability",
            "base_model_provider",
            "dataset_name",
            "dataset_version",
            "strategy",
            "status",
            "artifact_path",
            "metrics",
            "notes",
            "created_at",
            "updated_at",
        )


class FineTuneRunCreateSerializer(serializers.Serializer):
    base_model_id = serializers.IntegerField()
    dataset_name = serializers.CharField(max_length=255)
    dataset_version = serializers.CharField(required=False, allow_blank=True, max_length=128, default="")
    strategy = serializers.CharField(required=False, allow_blank=True, max_length=64, default="lora")
    status = serializers.ChoiceField(choices=FineTuneRun.STATUS_CHOICES, required=False, default=FineTuneRun.STATUS_PENDING)
    artifact_path = serializers.CharField(required=False, allow_blank=True, max_length=500, default="")
    metrics = serializers.DictField(required=False, default=dict)
    notes = serializers.CharField(required=False, allow_blank=True, default="")


class FineTuneRunUpdateSerializer(serializers.Serializer):
    dataset_name = serializers.CharField(required=False, allow_blank=False, max_length=255)
    dataset_version = serializers.CharField(required=False, allow_blank=True, max_length=128)
    strategy = serializers.CharField(required=False, allow_blank=True, max_length=64)
    status = serializers.ChoiceField(choices=FineTuneRun.STATUS_CHOICES, required=False)
    artifact_path = serializers.CharField(required=False, allow_blank=True, max_length=500)
    metrics = serializers.DictField(required=False)
    notes = serializers.CharField(required=False, allow_blank=True)
