"""
llm 应用的序列化器（类比 SpringBoot 中 @Valid + Jackson @JsonProperty 的 DTO 校验与转换层）。
该文件定义了所有请求/响应的数据结构和校验规则：
- 输入序列化器（Write/Create/Update/Test）用于校验请求体
- 输出序列化器（Summary）用于将模型实例转换为 JSON 响应

Django REST Framework 的 Serializer 承担了 SpringBoot 中 @RequestBody + @Valid + Jackson 的组合职责。
"""
from rest_framework import serializers

from llm.models import EvalRecord, FineTuneRun, FineTuneRunnerServer, ModelConfig

# 直接接入的供应商（不含 LiteLLM Legacy）
DIRECT_PROVIDER_CHOICES = (
    (ModelConfig.PROVIDER_DEEPSEEK, "DeepSeek"),
    (ModelConfig.PROVIDER_DASHSCOPE, "DashScope"),
    (ModelConfig.PROVIDER_OLLAMA, "Ollama"),
    (ModelConfig.PROVIDER_OPENAI_COMPATIBLE, "OpenAI Compatible"),
)


def _mask_api_key(value):
    """对 API Key 进行脱敏处理，仅显示部分字符。

    参数:
        value: 原始 API Key 字符串，可能为空。
    返回:
        脱敏后的字符串。长度 <= 10 时全部用 * 替换；否则保留前 6 位和后 4 位，中间用 ****** 替换。
    """
    if not value:
        return ""
    if len(value) <= 10:
        return "*" * len(value)
    return f"{value[:6]}******{value[-4:]}"


# ===================== 模型配置 序列化器 =====================

class ModelConfigSummarySerializer(serializers.ModelSerializer):
    """模型配置的输出序列化器（类比 SpringBoot 的 Response DTO）。

    在基础字段之上扩展了：脱敏后的 options、微调统计、路由别名、定价和调用次数等派生字段。
    所有 SerializerMethodField 对应的 get_xxx 方法用于动态计算这些派生值。
    """
    options = serializers.SerializerMethodField()
    has_api_key = serializers.SerializerMethodField()
    api_key_masked = serializers.SerializerMethodField()
    fine_tune_run_count = serializers.SerializerMethodField()
    latest_fine_tune_dataset = serializers.SerializerMethodField()
    latest_fine_tune_status = serializers.SerializerMethodField()
    latest_fine_tune_artifact_path = serializers.SerializerMethodField()
    alias = serializers.SerializerMethodField()
    upstream_provider = serializers.SerializerMethodField()
    upstream_model = serializers.SerializerMethodField()
    fallback_aliases = serializers.SerializerMethodField()
    weight = serializers.SerializerMethodField()
    input_price_per_million = serializers.SerializerMethodField()
    output_price_per_million = serializers.SerializerMethodField()
    request_price = serializers.SerializerMethodField()
    price_currency = serializers.SerializerMethodField()
    pricing_notes = serializers.SerializerMethodField()
    invocation_count = serializers.SerializerMethodField()

    def get_options(self, obj):
        """获取脱敏后的 options 配置。

        参数:
            obj: ModelConfig 模型实例。
        返回:
            dict，其中的 api_key 字段已脱敏。
        """
        options = dict(obj.options or {})
        if options.get("api_key"):
            options["api_key"] = _mask_api_key(options["api_key"])
        return options

    def get_has_api_key(self, obj):
        """判断是否配置了 API Key。

        参数:
            obj: ModelConfig 模型实例。
        返回:
            bool，是否包含非空 api_key。
        """
        return bool((obj.options or {}).get("api_key"))

    def get_api_key_masked(self, obj):
        """获取脱敏后的 API Key 字符串。

        参数:
            obj: ModelConfig 模型实例。
        返回:
            str，脱敏后的 API Key。
        """
        return _mask_api_key((obj.options or {}).get("api_key"))

    def _get_latest_fine_tune_run(self, obj):
        """内部辅助方法：获取该模型配置关联的最新一次微调记录。

        参数:
            obj: ModelConfig 模型实例。
        返回:
            FineTuneRun 实例或 None。
        """
        runs = getattr(obj, "fine_tune_runs", None)
        if runs is None:
            return None
        if hasattr(runs, "all"):
            return runs.all().order_by("-created_at", "-id").first()
        return None

    def get_fine_tune_run_count(self, obj):
        """获取该模型关联的微调运行次数。

        参数:
            obj: ModelConfig 实例。
        返回:
            int，微调运行总次数。
        """
        runs = getattr(obj, "fine_tune_runs", None)
        if runs is None or not hasattr(runs, "count"):
            return 0
        return runs.count()

    def get_latest_fine_tune_dataset(self, obj):
        """获取最新微调运行的数据集名称。

        参数:
            obj: ModelConfig 实例。
        返回:
            str，数据集名称或空字符串。
        """
        latest_run = self._get_latest_fine_tune_run(obj)
        return latest_run.dataset_name if latest_run else ""

    def get_latest_fine_tune_status(self, obj):
        """获取最新微调运行的状态。

        参数:
            obj: ModelConfig 实例。
        返回:
            str，状态值或空字符串。
        """
        latest_run = self._get_latest_fine_tune_run(obj)
        return latest_run.status if latest_run else ""

    def get_latest_fine_tune_artifact_path(self, obj):
        """获取最新微调运行的产物路径。

        参数:
            obj: ModelConfig 实例。
        返回:
            str，产物路径或空字符串。
        """
        latest_run = self._get_latest_fine_tune_run(obj)
        return latest_run.artifact_path if latest_run else ""

    def get_alias(self, obj):
        """获取别名（等同于 name）。

        参数:
            obj: ModelConfig 实例。
        返回:
            str，别名。
        """
        return obj.name

    def get_upstream_provider(self, obj):
        """获取上游供应商名称。

        参数:
            obj: ModelConfig 实例。
        返回:
            str，provider 值。
        """
        return obj.provider

    def get_upstream_model(self, obj):
        """获取上游模型名称。

        参数:
            obj: ModelConfig 实例。
        返回:
            str，model_name 值。
        """
        return obj.model_name

    def get_fallback_aliases(self, obj):
        """获取回退别名列表。

        参数:
            obj: ModelConfig 实例。
        返回:
            list，回退别名列表。
        """
        value = (obj.options or {}).get("fallback_aliases", [])
        return value if isinstance(value, list) else []

    def get_weight(self, obj):
        """获取路由权重。

        参数:
            obj: ModelConfig 实例。
        返回:
            int/float，权重值，默认为 1。
        """
        return (obj.options or {}).get("weight", 1)

    def get_input_price_per_million(self, obj):
        """获取输入价格（每百万 token）。

        参数:
            obj: ModelConfig 实例。
        返回:
            Decimal，输入单价。
        """
        return obj.input_price_per_million

    def get_output_price_per_million(self, obj):
        """获取输出价格（每百万 token）。

        参数:
            obj: ModelConfig 实例。
        返回:
            Decimal，输出单价。
        """
        return obj.output_price_per_million

    def get_request_price(self, obj):
        """获取按次请求价格。

        参数:
            obj: ModelConfig 实例。
        返回:
            Decimal，每次请求价格。
        """
        return obj.request_price

    def get_price_currency(self, obj):
        """获取定价货币。

        参数:
            obj: ModelConfig 实例。
        返回:
            str，货币代码。
        """
        return obj.price_currency

    def get_pricing_notes(self, obj):
        """获取定价备注。

        参数:
            obj: ModelConfig 实例。
        返回:
            str，定价备注文本。
        """
        return obj.pricing_notes

    def get_invocation_count(self, obj):
        """获取调用次数（通过 annotate 注入）。

        参数:
            obj: ModelConfig 实例。
        返回:
            int，调用总次数。
        """
        return getattr(obj, "invocation_count", 0)

    class Meta:
        model = ModelConfig
        fields = (
            "id",
            "name",
            "capability",
            "provider",
            "model_name",
            "parameter_scale",
            "endpoint",
            "description",
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
            "alias",
            "upstream_provider",
            "upstream_model",
            "fallback_aliases",
            "weight",
            "input_price_per_million",
            "output_price_per_million",
            "request_price",
            "price_currency",
            "pricing_notes",
            "invocation_count",
        )


class ModelConfigActivationSerializer(serializers.Serializer):
    """模型配置启用状态序列化器（用于 PATCH 切换启用/禁用）。"""
    is_active = serializers.BooleanField()


class ModelConfigWriteSerializer(serializers.Serializer):
    """模型配置写入序列化器（用于创建和完整更新）。

    类比 SpringBoot 中 @Valid 标注的 Request DTO。
    所有字段均进行基本校验（长度、类型、必填/可选）。
    """
    name = serializers.CharField(max_length=255)
    capability = serializers.ChoiceField(choices=ModelConfig.CAPABILITY_CHOICES)
    provider = serializers.ChoiceField(choices=DIRECT_PROVIDER_CHOICES)
    model_name = serializers.CharField(max_length=255)
    parameter_scale = serializers.CharField(required=False, allow_blank=True, max_length=64, default="")
    endpoint = serializers.URLField(max_length=500)
    description = serializers.CharField(required=False, allow_blank=True, default="")
    options = serializers.DictField(required=False, default=dict)
    input_price_per_million = serializers.DecimalField(
        required=False, max_digits=12, decimal_places=6, default=0
    )
    output_price_per_million = serializers.DecimalField(
        required=False, max_digits=12, decimal_places=6, default=0
    )
    request_price = serializers.DecimalField(required=False, max_digits=12, decimal_places=6, default=0)
    price_currency = serializers.CharField(required=False, allow_blank=True, max_length=8, default="USD")
    pricing_notes = serializers.CharField(required=False, allow_blank=True, default="")
    is_active = serializers.BooleanField(required=False, default=False)


class ModelConfigConnectionTestSerializer(serializers.Serializer):
    """模型连接测试序列化器（用于验证 API 端点是否可达）。"""
    model_config_id = serializers.IntegerField(required=False)
    provider = serializers.ChoiceField(choices=DIRECT_PROVIDER_CHOICES)
    model_name = serializers.CharField(max_length=255)
    endpoint = serializers.URLField(max_length=500)
    options = serializers.DictField(required=False, default=dict)


# ===================== Prompt 配置 序列化器 =====================

class PromptConfigSummarySerializer(serializers.Serializer):
    """Prompt 模板配置的输出序列化器。"""
    key = serializers.CharField()
    category = serializers.CharField()
    name = serializers.CharField()
    template = serializers.CharField()
    variables = serializers.ListField(child=serializers.CharField())
    updated_at = serializers.DateTimeField()


class PromptConfigUpdateSerializer(serializers.Serializer):
    """Prompt 模板更新序列化器（仅允许修改模板内容）。"""
    template = serializers.CharField()


# ===================== 评测 序列化器 =====================

class EvalRecordSummarySerializer(serializers.ModelSerializer):
    """评测记录的输出序列化器。"""
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
    """评测运行创建序列化器。"""
    task_type = serializers.ChoiceField(choices=EvalRecord.TASK_CHOICES)
    model_config_id = serializers.IntegerField(required=False)
    version = serializers.CharField(required=False, allow_blank=True, max_length=128)
    evaluation_mode = serializers.ChoiceField(choices=EvalRecord.EVALUATION_MODE_CHOICES, required=False, default=EvalRecord.EVALUATION_MODE_BASELINE)
    dataset_name = serializers.CharField(required=False, allow_blank=True, max_length=255, default="")
    dataset_version = serializers.CharField(required=False, allow_blank=True, max_length=128, default="")
    run_notes = serializers.CharField(required=False, allow_blank=True, default="")


# ===================== 微调 序列化器 =====================

class FineTuneRunnerServerSummarySerializer(serializers.ModelSerializer):
    """微调训练服务器的输出序列化器。"""
    has_auth_token = serializers.SerializerMethodField()
    auth_token_masked = serializers.SerializerMethodField()

    def get_has_auth_token(self, obj):
        """判断是否配置了认证令牌。

        参数:
            obj: FineTuneRunnerServer 实例。
        返回:
            bool，是否有 auth_token。
        """
        return bool(obj.auth_token)

    def get_auth_token_masked(self, obj):
        """获取脱敏后的认证令牌。

        参数:
            obj: FineTuneRunnerServer 实例。
        返回:
            str，脱敏后的令牌。
        """
        return _mask_api_key(obj.auth_token)

    class Meta:
        model = FineTuneRunnerServer
        fields = (
            "id",
            "name",
            "base_url",
            "default_work_dir",
            "is_enabled",
            "has_auth_token",
            "auth_token_masked",
            "created_at",
            "updated_at",
        )


class FineTuneRunnerServerWriteSerializer(serializers.Serializer):
    """微调训练服务器写入序列化器。"""
    name = serializers.CharField(max_length=255)
    base_url = serializers.URLField(max_length=500)
    auth_token = serializers.CharField(required=False, allow_blank=True, max_length=255)
    default_work_dir = serializers.CharField(required=False, allow_blank=True, max_length=500, default="")
    is_enabled = serializers.BooleanField(required=False, default=True)


class FineTuneRunSummarySerializer(serializers.ModelSerializer):
    """微调运行记录的输出序列化器。"""
    base_model_id = serializers.IntegerField(source="base_model.id")
    base_model_name = serializers.CharField(source="base_model.name")
    base_model_capability = serializers.CharField(source="base_model.capability")
    base_model_provider = serializers.CharField(source="base_model.provider")
    callback_token = serializers.SerializerMethodField()
    registered_model_config_id = serializers.IntegerField(source="registered_model_config.id", allow_null=True)
    runner_server_id = serializers.SerializerMethodField()
    runner_server_name = serializers.SerializerMethodField()

    def get_callback_token(self, obj):
        """获取回调令牌（优先取临时属性，否则取数据库字段）。

        参数:
            obj: FineTuneRun 实例。
        返回:
            str，回调令牌。
        """
        return getattr(obj, "callback_token", "") or getattr(obj, "callback_token_value", "")

    def get_runner_server_id(self, obj):
        """获取训练服务器 ID。

        参数:
            obj: FineTuneRun 实例。
        返回:
            int 或 None。
        """
        return obj.runner_server_id

    def get_runner_server_name(self, obj):
        """获取训练服务器名称。

        参数:
            obj: FineTuneRun 实例。
        返回:
            str，服务器名称或空字符串。
        """
        if obj.runner_server_id is None:
            return ""
        return obj.runner_server.name

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
            "run_key",
            "external_job_id",
            "runner_name",
            "runner_server_id",
            "runner_server_name",
            "artifact_path",
            "export_path",
            "deployment_endpoint",
            "deployment_model_name",
            "dataset_manifest",
            "training_config",
            "artifact_manifest",
            "metrics",
            "failure_reason",
            "queued_at",
            "started_at",
            "finished_at",
            "last_heartbeat_at",
            "callback_token",
            "registered_model_config_id",
            "notes",
            "created_at",
            "updated_at",
        )


class FineTuneRunCreateSerializer(serializers.Serializer):
    """微调运行记录创建序列化器。"""
    base_model_id = serializers.IntegerField()
    runner_server_id = serializers.IntegerField(required=False, allow_null=True)
    dataset_name = serializers.CharField(max_length=255)
    dataset_version = serializers.CharField(required=False, allow_blank=True, max_length=128, default="")
    strategy = serializers.CharField(required=False, allow_blank=True, max_length=64, default="lora")
    runner_name = serializers.CharField(required=False, allow_blank=True, max_length=128, default="")
    training_config = serializers.DictField(required=False, default=dict)
    notes = serializers.CharField(required=False, allow_blank=True, default="")


class FineTuneRunUpdateSerializer(serializers.Serializer):
    """微调运行记录更新序列化器。"""
    runner_server_id = serializers.IntegerField(required=False, allow_null=True)
    dataset_name = serializers.CharField(required=False, allow_blank=False, max_length=255)
    dataset_version = serializers.CharField(required=False, allow_blank=True, max_length=128)
    strategy = serializers.CharField(required=False, allow_blank=True, max_length=64)
    runner_name = serializers.CharField(required=False, allow_blank=True, max_length=128)
    training_config = serializers.DictField(required=False)
    status = serializers.ChoiceField(choices=FineTuneRun.STATUS_CHOICES, required=False)
    artifact_path = serializers.CharField(required=False, allow_blank=True, max_length=500)
    deployment_endpoint = serializers.CharField(required=False, allow_blank=True, max_length=500)
    deployment_model_name = serializers.CharField(required=False, allow_blank=True, max_length=255)
    metrics = serializers.DictField(required=False)
    artifact_manifest = serializers.DictField(required=False)
    failure_reason = serializers.CharField(required=False, allow_blank=True)
    notes = serializers.CharField(required=False, allow_blank=True)


class FineTuneRunCallbackSerializer(serializers.Serializer):
    """微调回调序列化器（由远程训练 Runner 回调使用）。"""
    status = serializers.ChoiceField(choices=FineTuneRun.STATUS_CHOICES, required=False)
    external_job_id = serializers.CharField(required=False, allow_blank=True, max_length=255)
    metrics = serializers.DictField(required=False, default=dict)
    artifact_manifest = serializers.DictField(required=False, default=dict)
    deployment_endpoint = serializers.CharField(required=False, allow_blank=True, max_length=500)
    deployment_model_name = serializers.CharField(required=False, allow_blank=True, max_length=255)
    failure_reason = serializers.CharField(required=False, allow_blank=True, default="")
