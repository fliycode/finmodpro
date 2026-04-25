from django.conf import settings
from django.db import models, transaction


class ModelConfig(models.Model):
    CAPABILITY_CHAT = "chat"
    CAPABILITY_EMBEDDING = "embedding"
    CAPABILITY_RERANK = "rerank"
    CAPABILITY_CHOICES = (
        (CAPABILITY_CHAT, "Chat"),
        (CAPABILITY_EMBEDDING, "Embedding"),
        (CAPABILITY_RERANK, "Rerank"),
    )

    PROVIDER_OLLAMA = "ollama"
    PROVIDER_DEEPSEEK = "deepseek"
    PROVIDER_LITELLM = "litellm"
    PROVIDER_DASHSCOPE = "dashscope"
    PROVIDER_CHOICES = (
        (PROVIDER_OLLAMA, "Ollama"),
        (PROVIDER_DEEPSEEK, "DeepSeek"),
        (PROVIDER_LITELLM, "LiteLLM"),
        (PROVIDER_DASHSCOPE, "DashScope"),
    )

    name = models.CharField(max_length=255)
    capability = models.CharField(max_length=32, choices=CAPABILITY_CHOICES)
    provider = models.CharField(max_length=32, choices=PROVIDER_CHOICES)
    model_name = models.CharField(max_length=255)
    endpoint = models.URLField(max_length=500)
    options = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["capability", "id"]
        unique_together = ("capability", "name")

    def save(self, *args, **kwargs):
        with transaction.atomic():
            super().save(*args, **kwargs)
            if self.is_active:
                self.__class__.objects.filter(capability=self.capability).exclude(
                    id=self.id
                ).update(is_active=False)


class EvalRecord(models.Model):
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
    target_name = models.CharField(max_length=255, db_index=True)
    task_type = models.CharField(max_length=64, choices=TASK_CHOICES, db_index=True)
    qa_accuracy = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        blank=True,
        null=True,
    )
    extraction_accuracy = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        blank=True,
        null=True,
    )
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
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]


class FineTuneRun(models.Model):
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
    run_key = models.CharField(max_length=64, blank=True, default="", db_index=True)
    external_job_id = models.CharField(max_length=255, blank=True, default="", db_index=True)
    runner_name = models.CharField(max_length=128, blank=True, default="")
    dataset_name = models.CharField(max_length=255)
    dataset_version = models.CharField(max_length=128, blank=True, default="")
    strategy = models.CharField(max_length=64, default="lora")
    status = models.CharField(
        max_length=32,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
        db_index=True,
    )
    artifact_path = models.CharField(max_length=500, blank=True, default="")
    export_path = models.CharField(max_length=500, blank=True, default="")
    deployment_endpoint = models.CharField(max_length=500, blank=True, default="")
    deployment_model_name = models.CharField(max_length=255, blank=True, default="")
    callback_token_hash = models.CharField(max_length=128, blank=True, default="")
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


class LiteLLMSyncEvent(models.Model):
    STATUS_SUCCESS = "success"
    STATUS_FAILED = "failed"

    status = models.CharField(max_length=32)
    triggered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    message = models.TextField(blank=True, default="")
    checksum = models.CharField(max_length=128, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]


class ModelInvocationLog(models.Model):
    model_config = models.ForeignKey(
        ModelConfig,
        related_name="invocation_logs",
        on_delete=models.CASCADE,
    )
    capability = models.CharField(max_length=32, choices=ModelConfig.CAPABILITY_CHOICES)
    provider = models.CharField(max_length=32, default=ModelConfig.PROVIDER_LITELLM)
    alias = models.CharField(max_length=255)
    upstream_model = models.CharField(max_length=255, blank=True, default="")
    stage = models.CharField(max_length=32, blank=True, default="")
    status = models.CharField(max_length=32, default="success")
    latency_ms = models.PositiveIntegerField(default=0)
    request_tokens = models.PositiveIntegerField(default=0)
    response_tokens = models.PositiveIntegerField(default=0)
    error_code = models.CharField(max_length=64, blank=True, default="")
    error_message = models.TextField(blank=True, default="")
    trace_id = models.CharField(max_length=128, blank=True, default="", db_index=True)
    request_id = models.CharField(max_length=128, blank=True, default="", db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["model_config", "-created_at"]),
            models.Index(fields=["trace_id", "-created_at"]),
        ]
