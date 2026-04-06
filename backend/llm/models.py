from django.db import models, transaction


class ModelConfig(models.Model):
    CAPABILITY_CHAT = "chat"
    CAPABILITY_EMBEDDING = "embedding"
    CAPABILITY_CHOICES = (
        (CAPABILITY_CHAT, "Chat"),
        (CAPABILITY_EMBEDDING, "Embedding"),
    )

    PROVIDER_OLLAMA = "ollama"
    PROVIDER_DEEPSEEK = "deepseek"
    PROVIDER_CHOICES = (
        (PROVIDER_OLLAMA, "Ollama"),
        (PROVIDER_DEEPSEEK, "DeepSeek"),
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
    average_latency_ms = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    version = models.CharField(max_length=128, blank=True, default="")
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
