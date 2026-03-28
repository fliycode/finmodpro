from django.db import models


class RetrievalLog(models.Model):
    SOURCE_RETRIEVAL_API = "retrieval_api"
    SOURCE_CHAT_ASK = "chat_ask"
    SOURCE_CHOICES = (
        (SOURCE_RETRIEVAL_API, "Retrieval API"),
        (SOURCE_CHAT_ASK, "Chat Ask"),
    )

    query = models.TextField()
    top_k = models.PositiveIntegerField(default=5)
    filters = models.JSONField(default=dict, blank=True)
    result_count = models.PositiveIntegerField(default=0)
    source = models.CharField(
        max_length=32,
        choices=SOURCE_CHOICES,
        default=SOURCE_RETRIEVAL_API,
    )
    metadata = models.JSONField(default=dict, blank=True)
    duration_ms = models.PositiveIntegerField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]


RetrievalAuditLog = RetrievalLog
