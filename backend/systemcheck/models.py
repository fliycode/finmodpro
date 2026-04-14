from django.conf import settings
from django.db import models


class AuditRecord(models.Model):
    STATUS_SUCCEEDED = "succeeded"
    STATUS_FAILED = "failed"
    STATUS_RETRIED = "retried"
    STATUS_SKIPPED = "skipped"
    STATUS_CHOICES = (
        (STATUS_SUCCEEDED, "Succeeded"),
        (STATUS_FAILED, "Failed"),
        (STATUS_RETRIED, "Retried"),
        (STATUS_SKIPPED, "Skipped"),
    )

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="audit_records",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
    )
    action = models.CharField(max_length=128, db_index=True)
    target_type = models.CharField(max_length=64, db_index=True)
    target_id = models.CharField(max_length=64, blank=True, default="", db_index=True)
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, db_index=True)
    detail_payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
