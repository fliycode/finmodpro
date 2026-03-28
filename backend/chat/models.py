from django.conf import settings
from django.db import models


class ChatSession(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="chat_sessions",
        on_delete=models.CASCADE,
    )
    title = models.CharField(max_length=255, default="新会话")
    context_filters = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at", "-id"]

