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

