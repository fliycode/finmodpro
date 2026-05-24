"""
llm 应用的数据模型（类比 SpringBoot 中 JPA/Hibernate 的 @Entity）。
该文件定义了 LLM 管理面所需的所有数据库表：
- ModelConfig: 模型配置（对应 @Entity，一条记录代表一个已接入的 LLM 模型）
- EvalRecord: 评测记录（存储每次评测运行的指标）
- FineTuneRunnerServer: 微调训练服务器配置
- FineTuneRun: 微调运行记录（一次微调任务的完整生命周期）
- ModelInvocationLog: 模型调用日志（每次实际 API 调用的审计/计费记录）

Django ORM 自动通过 Meta 类生成数据库索引、约束和表名。
"""
from django.db import models, transaction


class ModelConfig(models.Model):
    """模型配置实体（类比 SpringBoot 的 @Entity）。

    字段类比：
    - name: 别名，便于人工辨识
    - capability: 能力类型（chat / embedding / rerank）
    - provider: 供应商名称
    - model_name: 上游模型标识
    - endpoint: API 端点 URL
    - options: JSON 扩展配置（如 api_key、fallback_aliases 等）
    - input_price_per_million / output_price_per_million / request_price: 定价信息
    - is_active: 是否启用（同一 capability 下只能启用一个）
    """
    CAPABILITY_CHAT = "chat"          # 对话能力
    CAPABILITY_EMBEDDING = "embedding"  # 向量嵌入能力
    CAPABILITY_RERANK = "rerank"      # 重排序能力
    CAPABILITY_CHOICES = (
        (CAPABILITY_CHAT, "Chat"),
        (CAPABILITY_EMBEDDING, "Embedding"),
        (CAPABILITY_RERANK, "Rerank"),
    )

    PROVIDER_OLLAMA = "ollama"
    PROVIDER_DEEPSEEK = "deepseek"
    PROVIDER_LITELLM = "litellm"
    PROVIDER_DASHSCOPE = "dashscope"
    PROVIDER_OPENAI_COMPATIBLE = "openai_compatible"
    PROVIDER_CHOICES = (
        (PROVIDER_OLLAMA, "Ollama"),
        (PROVIDER_DEEPSEEK, "DeepSeek"),
        (PROVIDER_DASHSCOPE, "DashScope"),
        (PROVIDER_OPENAI_COMPATIBLE, "OpenAI Compatible"),
        (PROVIDER_LITELLM, "LiteLLM (Legacy)"),
    )

    name = models.CharField(max_length=255)
    capability = models.CharField(max_length=32, choices=CAPABILITY_CHOICES)
    provider = models.CharField(max_length=32, choices=PROVIDER_CHOICES)
    model_name = models.CharField(max_length=255)
    parameter_scale = models.CharField(max_length=64, blank=True, default="")
    endpoint = models.URLField(max_length=500)
    description = models.TextField(blank=True, default="")
    options = models.JSONField(default=dict, blank=True)
    input_price_per_million = models.DecimalField(max_digits=12, decimal_places=6, default=0)
    output_price_per_million = models.DecimalField(max_digits=12, decimal_places=6, default=0)
    request_price = models.DecimalField(max_digits=12, decimal_places=6, default=0)
    price_currency = models.CharField(max_length=8, blank=True, default="USD")
    pricing_notes = models.TextField(blank=True, default="")
    is_active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["capability", "id"]
        unique_together = ("capability", "name")

    def save(self, *args, **kwargs):
        """保存模型配置，并确保同一 capability 下最多只有一个启用项。

        在事务中执行：先保存自身，若被标记为 is_active，则将该 capability 下其他配置的 is_active 置为 False。
        类比 SpringBoot 中 @Transactional 方法，保证同一能力类型下仅一个活跃配置。
        """
        with transaction.atomic():
            super().save(*args, **kwargs)
            if self.is_active:
                self.__class__.objects.filter(capability=self.capability).exclude(id=self.id).update(is_active=False)


class EvalRecord(models.Model):
    """评测记录实体。

    存储每次模型评测的结果，包括准确率、延迟等指标。
    支持三种评测模式：baseline（基准）、rag（检索增强生成）、fine_tuned（微调）。
    """
    EVALUATION_MODE_BASELINE = "baseline"
    EVALUATION_MODE_RAG = "rag"
    EVALUATION_MODE_FINE_TUNED = "fine_tuned"
    EVALUATION_MODE_CHOICES = (
        (EVALUATION_MODE_BASELINE, "Baseline"),
        (EVALUATION_MODE_RAG, "RAG"),
        (EVALUATION_MODE_FINE_TUNED, "Fine-tuned"),
    )

    TASK_QA = "qa"
    TASK_RISK_EXTRACTION = "risk_extraction"
    TASK_REPORT = "report"
    TASK_CHOICES = (
        (TASK_QA, "QA"),
        (TASK_RISK_EXTRACTION, "Risk Extraction"),
        (TASK_REPORT, "Report"),
    )

    STATUS_PENDING = "pending"
    STATUS_RUNNING = "running"
    STATUS_SUCCEEDED = "succeeded"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = (
        (STATUS_PENDING, "Pending"),
        (STATUS_RUNNING, "Running"),
        (STATUS_SUCCEEDED, "Succeeded"),
        (STATUS_FAILED, "Failed"),
    )

    model_config = models.ForeignKey(
        ModelConfig,
        related_name="eval_records",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
    )
    evaluation_mode = models.CharField(
        max_length=32,
        choices=EVALUATION_MODE_CHOICES,
        default=EVALUATION_MODE_BASELINE,
        db_index=True,
    )
    target_name = models.CharField(max_length=255, db_index=True)     # 评测目标名称
    task_type = models.CharField(max_length=64, choices=TASK_CHOICES, db_index=True)
    qa_accuracy = models.DecimalField(max_digits=5, decimal_places=4, blank=True, null=True)
    extraction_accuracy = models.DecimalField(max_digits=5, decimal_places=4, blank=True, null=True)
    precision = models.DecimalField(max_digits=5, decimal_places=4, blank=True, null=True)
    recall = models.DecimalField(max_digits=5, decimal_places=4, blank=True, null=True)
    f1_score = models.DecimalField(max_digits=5, decimal_places=4, blank=True, null=True)
    average_latency_ms = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    version = models.CharField(max_length=128, blank=True, default="")
    dataset_name = models.CharField(max_length=255, blank=True, default="", db_index=True)
    dataset_version = models.CharField(max_length=128, blank=True, default="")
    run_notes = models.TextField(blank=True, default="")
    status = models.CharField(
        max_length=32,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
        db_index=True,
    )
    metadata = models.JSONField(default=dict, blank=True)   # 扩展元数据（评测器类型、数据集大小等）
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]


class FineTuneRunnerServer(models.Model):
    """微调训练服务器配置实体。

    存储远程微调执行器（如 LLaMA-Factory Runner）的连接信息。
    """
    name = models.CharField(max_length=255, unique=True)
    base_url = models.URLField(max_length=500)            # 训练服务器 API 基地址
    auth_token = models.CharField(max_length=255, blank=True, default="")  # 认证令牌
    default_work_dir = models.CharField(max_length=500, blank=True, default="")  # 默认工作目录
    is_enabled = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name", "id"]


class FineTuneRun(models.Model):
    """微调运行记录实体。

    存储一次微调任务从创建、派发、执行到完成的完整生命周期状态。
    包含数据集信息、训练配置、产物路径、回调令牌等。
    """
    STATUS_PENDING = "pending"
    STATUS_RUNNING = "running"
    STATUS_SUCCEEDED = "succeeded"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = (
        (STATUS_PENDING, "Pending"),
        (STATUS_RUNNING, "Running"),
        (STATUS_SUCCEEDED, "Succeeded"),
        (STATUS_FAILED, "Failed"),
    )

    base_model = models.ForeignKey(
        ModelConfig,
        related_name="fine_tune_runs",
        on_delete=models.CASCADE,
    )
    registered_model_config = models.ForeignKey(
        ModelConfig,
        related_name="registered_fine_tune_runs",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
    )
    runner_server = models.ForeignKey(
        FineTuneRunnerServer,
        related_name="fine_tune_runs",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
    )
    run_key = models.CharField(max_length=64, blank=True, default="", db_index=True)   # 运行唯一标识
    external_job_id = models.CharField(max_length=255, blank=True, default="", db_index=True)  # 外部任务 ID
    runner_name = models.CharField(max_length=128, blank=True, default="")
    dataset_name = models.CharField(max_length=255)
    dataset_version = models.CharField(max_length=128, blank=True, default="")
    strategy = models.CharField(max_length=64, default="lora")   # 微调策略（lora / full）
    status = models.CharField(
        max_length=32,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
        db_index=True,
    )
    artifact_path = models.CharField(max_length=500, blank=True, default="")   # 产物路径
    export_path = models.CharField(max_length=500, blank=True, default="")     # 导出路径
    deployment_endpoint = models.CharField(max_length=500, blank=True, default="")  # 部署端点
    deployment_model_name = models.CharField(max_length=255, blank=True, default="")  # 部署模型名
    callback_token_hash = models.CharField(max_length=128, blank=True, default="")   # 回调令牌哈希
    callback_token_value = models.CharField(max_length=255, blank=True, default="")   # 回调令牌明文（仅供创建时返回）
    dataset_manifest = models.JSONField(default=dict, blank=True)
    training_config = models.JSONField(default=dict, blank=True)
    artifact_manifest = models.JSONField(default=dict, blank=True)
    metrics = models.JSONField(default=dict, blank=True)
    queued_at = models.DateTimeField(blank=True, null=True, db_index=True)
    started_at = models.DateTimeField(blank=True, null=True)
    finished_at = models.DateTimeField(blank=True, null=True)
    last_heartbeat_at = models.DateTimeField(blank=True, null=True)
    failure_reason = models.TextField(blank=True, default="")
    notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]


class ModelInvocationLog(models.Model):
    """模型调用日志实体。

    每次通过网关或直接调用 LLM API 时记录一条日志，用于计费、监控和审计。
    类比 SpringBoot 中的审计/日志实体，支持按时间、模型、trace_id 等维度查询。
    """
    STATUS_SUCCESS = "success"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = (
        (STATUS_SUCCESS, "Success"),
        (STATUS_FAILED, "Failed"),
    )
    TOKEN_SOURCE_PROVIDER = "provider"
    TOKEN_SOURCE_ESTIMATED = "estimated"
    TOKEN_SOURCE_NONE = "none"
    TOKEN_SOURCE_CHOICES = (
        (TOKEN_SOURCE_PROVIDER, "Provider"),
        (TOKEN_SOURCE_ESTIMATED, "Estimated"),
        (TOKEN_SOURCE_NONE, "None"),
    )

    STAGE_ROUTING = "routing"
    STAGE_FALLBACK = "fallback"
    STAGE_DIRECT = "direct"
    STAGE_CHOICES = (
        (STAGE_ROUTING, "Routing"),
        (STAGE_FALLBACK, "Fallback"),
        (STAGE_DIRECT, "Direct"),
    )

    model_config = models.ForeignKey(
        ModelConfig,
        related_name="invocation_logs",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    capability = models.CharField(max_length=32, choices=ModelConfig.CAPABILITY_CHOICES)
    provider = models.CharField(
        max_length=32,
        choices=ModelConfig.PROVIDER_CHOICES,
        default=ModelConfig.PROVIDER_OPENAI_COMPATIBLE,
    )
    alias = models.CharField(max_length=255)           # 别名（关联到 ModelConfig.name）
    upstream_model = models.CharField(max_length=255, blank=True, default="")  # 上游模型标识
    # stage: 可选流水线步骤标签；为空表示未分类（例如网关外部的直接 SDK 调用）
    stage = models.CharField(max_length=32, choices=STAGE_CHOICES, blank=True, default="")
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default=STATUS_SUCCESS)
    latency_ms = models.PositiveIntegerField(default=0)  # 调用延迟（毫秒）
    request_tokens = models.PositiveIntegerField(default=0)
    response_tokens = models.PositiveIntegerField(default=0)
    total_tokens = models.PositiveIntegerField(default=0)
    token_source = models.CharField(
        max_length=32,
        choices=TOKEN_SOURCE_CHOICES,
        default=TOKEN_SOURCE_NONE,
    )
    raw_usage = models.JSONField(default=dict, blank=True)  # 原始用量数据
    provider_request_id = models.CharField(max_length=128, blank=True, default="")
    input_unit_price_snapshot = models.DecimalField(max_digits=12, decimal_places=6, default=0)
    output_unit_price_snapshot = models.DecimalField(max_digits=12, decimal_places=6, default=0)
    request_price_snapshot = models.DecimalField(max_digits=12, decimal_places=6, default=0)
    input_cost = models.DecimalField(max_digits=18, decimal_places=8, default=0)
    output_cost = models.DecimalField(max_digits=18, decimal_places=8, default=0)
    total_cost = models.DecimalField(max_digits=18, decimal_places=8, default=0)
    error_code = models.CharField(max_length=64, blank=True, default="")
    error_message = models.TextField(blank=True, default="")
    trace_id = models.CharField(max_length=128, blank=True, default="")    # 链路追踪 ID
    request_id = models.CharField(max_length=128, blank=True, default="")  # 请求 ID
    # created_at 上有 db_index=True，支持默认按时间倒排及不包含复合索引前缀列的按时间范围查询
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["provider", "-created_at"], name="llm_invlog_prov_created_idx"),
            models.Index(fields=["model_config", "-created_at"], name="llm_invoclog_cfg_created_idx"),
            models.Index(fields=["trace_id", "-created_at"], name="llm_invoclog_trace_created_idx"),
            models.Index(fields=["request_id", "-created_at"], name="llm_invoclog_reqid_created_idx"),
        ]
