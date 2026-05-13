import uuid

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from knowledgebase.models import Document, DocumentChunk


class RiskEvent(models.Model):
    LEVEL_LOW = "low"
    LEVEL_MEDIUM = "medium"
    LEVEL_HIGH = "high"
    LEVEL_CRITICAL = "critical"
    LEVEL_CHOICES = (
        (LEVEL_LOW, "Low"),
        (LEVEL_MEDIUM, "Medium"),
        (LEVEL_HIGH, "High"),
        (LEVEL_CRITICAL, "Critical"),
    )

    STATUS_PENDING = "pending"
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected"
    STATUS_CHOICES = (
        (STATUS_PENDING, "Pending"),
        (STATUS_APPROVED, "Approved"),
        (STATUS_REJECTED, "Rejected"),
    )

    company_name = models.CharField(max_length=255, db_index=True)
    risk_type = models.CharField(max_length=128, db_index=True)
    risk_level = models.CharField(
        max_length=32,
        choices=LEVEL_CHOICES,
        default=LEVEL_MEDIUM,
        db_index=True,
    )
    event_time = models.DateTimeField(blank=True, null=True, db_index=True)
    summary = models.TextField()
    evidence_text = models.TextField()
    confidence_score = models.DecimalField(
        max_digits=4,
        decimal_places=3,
        validators=[MinValueValidator(0), MaxValueValidator(1)],
    )
    review_status = models.CharField(
        max_length=32,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
        db_index=True,
    )
    document = models.ForeignKey(
        Document,
        related_name="risk_events",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
    )
    chunk = models.ForeignKey(
        DocumentChunk,
        related_name="risk_events",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
    )
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]


class RiskReport(models.Model):
    SCOPE_COMPANY = "company"
    SCOPE_TIME_RANGE = "time_range"
    SCOPE_CHOICES = (
        (SCOPE_COMPANY, "Company"),
        (SCOPE_TIME_RANGE, "Time Range"),
    )

    scope_type = models.CharField(
        max_length=32,
        choices=SCOPE_CHOICES,
        db_index=True,
    )
    title = models.CharField(max_length=255)
    company_name = models.CharField(max_length=255, blank=True, null=True, db_index=True)
    period_start = models.DateField(blank=True, null=True, db_index=True)
    period_end = models.DateField(blank=True, null=True, db_index=True)
    summary = models.TextField(blank=True)
    content = models.TextField()
    source_metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]


class RiskExtractionTask(models.Model):
    STATUS_QUEUED = "queued"
    STATUS_RUNNING = "running"
    STATUS_SUCCEEDED = "succeeded"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = (
        (STATUS_QUEUED, "Queued"),
        (STATUS_RUNNING, "Running"),
        (STATUS_SUCCEEDED, "Succeeded"),
        (STATUS_FAILED, "Failed"),
    )

    STEP_QUEUED = "queued"
    STEP_EXTRACTING = "extracting"
    STEP_COMPLETED = "completed"
    STEP_FAILED = "failed"
    STEP_CHOICES = (
        (STEP_QUEUED, "Queued"),
        (STEP_EXTRACTING, "Extracting"),
        (STEP_COMPLETED, "Completed"),
        (STEP_FAILED, "Failed"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.ForeignKey(
        Document,
        related_name="risk_extraction_tasks",
        on_delete=models.CASCADE,
    )
    celery_task_id = models.CharField(max_length=255, blank=True, db_index=True)
    status = models.CharField(
        max_length=32,
        choices=STATUS_CHOICES,
        default=STATUS_QUEUED,
    )
    current_step = models.CharField(
        max_length=32,
        choices=STEP_CHOICES,
        default=STEP_QUEUED,
    )
    progress = models.PositiveSmallIntegerField(default=6)
    created_count = models.PositiveIntegerField(default=0)
    message = models.TextField(blank=True)
    error_message = models.TextField(blank=True)
    result_payload = models.JSONField(default=dict, blank=True)
    started_at = models.DateTimeField(blank=True, null=True)
    finished_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-updated_at"]
