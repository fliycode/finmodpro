from django.db import models


class RetrievalAuditLog(models.Model):
    query = models.TextField()
    filters = models.JSONField(default=dict, blank=True)
    result_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
