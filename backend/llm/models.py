from django.db import models, transaction


class ModelConfig(models.Model):
    CAPABILITY_CHAT = "chat"
    CAPABILITY_EMBEDDING = "embedding"
    CAPABILITY_CHOICES = (
        (CAPABILITY_CHAT, "Chat"),
        (CAPABILITY_EMBEDDING, "Embedding"),
    )

    PROVIDER_OLLAMA = "ollama"
    PROVIDER_CHOICES = (
        (PROVIDER_OLLAMA, "Ollama"),
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

