from django.conf import settings
from django.db import models
from django.db.models import Max


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


class ChatMessage(models.Model):
    ROLE_USER = "user"
    ROLE_ASSISTANT = "assistant"
    ROLE_SYSTEM = "system"
    ROLE_CHOICES = (
        (ROLE_USER, "User"),
        (ROLE_ASSISTANT, "Assistant"),
        (ROLE_SYSTEM, "System"),
    )

    TYPE_TEXT = "text"
    TYPE_CHOICES = (
        (TYPE_TEXT, "Text"),
    )

    session = models.ForeignKey(
        ChatSession,
        related_name="messages",
        on_delete=models.CASCADE,
    )
    sequence = models.PositiveIntegerField(blank=True, null=True)
    role = models.CharField(max_length=32, choices=ROLE_CHOICES)
    message_type = models.CharField(
        max_length=32,
        choices=TYPE_CHOICES,
        default=TYPE_TEXT,
    )
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sequence", "id"]
        unique_together = ("session", "sequence")

    def save(self, *args, **kwargs):
        if self.sequence is None:
            last_sequence = (
                self.__class__.objects.filter(session=self.session).aggregate(
                    max_sequence=Max("sequence")
                )["max_sequence"]
                or 0
            )
            self.sequence = last_sequence + 1
        super().save(*args, **kwargs)
