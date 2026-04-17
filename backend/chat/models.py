from django.conf import settings
from django.db import models
from django.db.models import Max


class ChatSession(models.Model):
    TITLE_STATUS_PENDING = "pending"
    TITLE_STATUS_READY = "ready"
    TITLE_STATUS_FAILED = "failed"
    TITLE_STATUS_CHOICES = (
        (TITLE_STATUS_PENDING, "Pending"),
        (TITLE_STATUS_READY, "Ready"),
        (TITLE_STATUS_FAILED, "Failed"),
    )
    TITLE_SOURCE_AI = "ai"
    TITLE_SOURCE_MANUAL = "manual"
    TITLE_SOURCE_LEGACY = "legacy"
    TITLE_SOURCE_SYSTEM = "system"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="chat_sessions",
        on_delete=models.CASCADE,
    )
    title = models.CharField(max_length=255, default="新会话")
    title_status = models.CharField(
        max_length=16,
        choices=TITLE_STATUS_CHOICES,
        default=TITLE_STATUS_PENDING,
    )
    title_source = models.CharField(max_length=32, default=TITLE_SOURCE_AI)
    rolling_summary = models.TextField(blank=True, default="")
    summary_updated_through_message_id = models.PositiveBigIntegerField(blank=True, null=True)
    message_count = models.PositiveIntegerField(default=0)
    last_message_at = models.DateTimeField(blank=True, null=True)
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

    STATUS_PENDING = "pending"
    STATUS_COMPLETE = "complete"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = (
        (STATUS_PENDING, "Pending"),
        (STATUS_COMPLETE, "Complete"),
        (STATUS_FAILED, "Failed"),
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
    status = models.CharField(
        max_length=16,
        choices=STATUS_CHOICES,
        default=STATUS_COMPLETE,
    )
    citations_json = models.JSONField(default=list, blank=True)
    model_metadata_json = models.JSONField(default=dict, blank=True)
    client_message_id = models.CharField(max_length=64, blank=True, default="")
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


class MemoryItem(models.Model):
    SCOPE_USER_GLOBAL = "user_global"
    SCOPE_PROJECT = "project"
    SCOPE_DATASET = "dataset"
    SCOPE_CHOICES = (
        (SCOPE_USER_GLOBAL, "User Global"),
        (SCOPE_PROJECT, "Project"),
        (SCOPE_DATASET, "Dataset"),
    )

    TYPE_USER_PREFERENCE = "user_preference"
    TYPE_PROJECT_BACKGROUND = "project_background"
    TYPE_CONFIRMED_FACT = "confirmed_fact"
    TYPE_WORK_RULE = "work_rule"
    TYPE_CHOICES = (
        (TYPE_USER_PREFERENCE, "User Preference"),
        (TYPE_PROJECT_BACKGROUND, "Project Background"),
        (TYPE_CONFIRMED_FACT, "Confirmed Fact"),
        (TYPE_WORK_RULE, "Work Rule"),
    )

    SOURCE_AUTO = "auto"
    SOURCE_MANUAL = "manual"
    SOURCE_CHOICES = (
        (SOURCE_AUTO, "Auto"),
        (SOURCE_MANUAL, "Manual"),
    )

    STATUS_ACTIVE = "active"
    STATUS_ARCHIVED = "archived"
    STATUS_DELETED = "deleted"
    STATUS_CHOICES = (
        (STATUS_ACTIVE, "Active"),
        (STATUS_ARCHIVED, "Archived"),
        (STATUS_DELETED, "Deleted"),
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="memory_items",
        on_delete=models.CASCADE,
    )
    scope_type = models.CharField(max_length=32, choices=SCOPE_CHOICES)
    scope_key = models.CharField(max_length=255, blank=True, default="")
    memory_type = models.CharField(max_length=32, choices=TYPE_CHOICES)
    title = models.CharField(max_length=255)
    content = models.TextField()
    confidence_score = models.DecimalField(max_digits=4, decimal_places=2, default=0.0)
    source_kind = models.CharField(
        max_length=16,
        choices=SOURCE_CHOICES,
        default=SOURCE_AUTO,
    )
    status = models.CharField(
        max_length=16,
        choices=STATUS_CHOICES,
        default=STATUS_ACTIVE,
    )
    pinned = models.BooleanField(default=False)
    fingerprint = models.CharField(max_length=255, blank=True, default="")
    last_verified_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-pinned", "-updated_at", "-id"]


class MemoryEvidence(models.Model):
    CONFIRMATION_PENDING = "pending"
    CONFIRMATION_CONFIRMED = "confirmed"
    CONFIRMATION_REJECTED = "rejected"
    CONFIRMATION_CHOICES = (
        (CONFIRMATION_PENDING, "Pending"),
        (CONFIRMATION_CONFIRMED, "Confirmed"),
        (CONFIRMATION_REJECTED, "Rejected"),
    )

    memory_item = models.ForeignKey(
        MemoryItem,
        related_name="evidence_items",
        on_delete=models.CASCADE,
    )
    session = models.ForeignKey(
        ChatSession,
        related_name="memory_evidence_items",
        on_delete=models.CASCADE,
        blank=True,
        null=True,
    )
    message = models.ForeignKey(
        ChatMessage,
        related_name="memory_evidence_items",
        on_delete=models.CASCADE,
        blank=True,
        null=True,
    )
    evidence_excerpt = models.TextField(blank=True, default="")
    extractor_version = models.CharField(max_length=64, blank=True, default="")
    confirmation_status = models.CharField(
        max_length=16,
        choices=CONFIRMATION_CHOICES,
        default=CONFIRMATION_PENDING,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(session__isnull=False) | models.Q(message__isnull=False),
                name="chat_memoryevidence_requires_source",
            )
        ]


class MemoryActionLog(models.Model):
    ACTION_VIEW = "view"
    ACTION_DELETE = "delete"
    ACTION_PIN = "pin"
    ACTION_UNPIN = "unpin"
    ACTION_MANUAL_ADD = "manual_add"
    ACTION_MANUAL_EDIT = "manual_edit"
    ACTION_CHOICES = (
        (ACTION_VIEW, "View"),
        (ACTION_DELETE, "Delete"),
        (ACTION_PIN, "Pin"),
        (ACTION_UNPIN, "Unpin"),
        (ACTION_MANUAL_ADD, "Manual Add"),
        (ACTION_MANUAL_EDIT, "Manual Edit"),
    )

    memory_item = models.ForeignKey(
        MemoryItem,
        related_name="action_logs",
        on_delete=models.CASCADE,
    )
    actor_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="memory_action_logs",
        on_delete=models.CASCADE,
    )
    action = models.CharField(max_length=32, choices=ACTION_CHOICES)
    details_json = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
