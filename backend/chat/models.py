"""
Chat 应用数据模型层。

类比 SpringBoot：
  - Django Model 相当于 JPA Entity（@Entity 注解的 Java 类）。
  - models.CharField / models.TextField 等字段类型类比 @Column 注解定义的列。
  - ForeignKey 相当于 @ManyToOne 或 @OneToMany 关系映射。
  - Meta 内部类相当于 @Table 注解中的索引/排序/约束定义。
  - Django ORM（objects.filter / objects.create）相当于 Spring Data JPA 的 Repository 自动生成方法。

本模块定义了聊天系统的核心实体：
  - ChatSession： 聊天会话（类比会话线程/Conversation）
  - ChatMessage： 聊天消息（类比会话中的一条 Message）
  - MemoryItem： 长期记忆条目（类比用户偏好/知识存储单元）
  - MemoryEvidence： 记忆证据（关联记忆与原文来源的佐证记录）
  - MemoryActionLog： 记忆操作审计日志（类比操作审计日志表）
"""

from django.conf import settings
from django.db import models
from django.db.models import Max


class ChatSession(models.Model):
    """
    聊天会话实体。

    类比 SpringBoot：
      - 相当于一个 JPA Entity，映射到 chat_session 表。
      - 每条记录代表用户发起的一次对话会话。

    字段：
      - user: 所属用户（外键 -> AUTH_USER_MODEL），相当于 @ManyToOne 关联 User 实体。
      - title: 会话标题，默认"新会话"。
      - title_status: 标题生成状态（pending/ready/failed）。
      - title_source: 标题来源（ai/manual/legacy/system）。
      - rolling_summary: 滚动摘要（渐进式会话摘要文本）。
      - summary_updated_through_message_id: 摘要已更新到哪条消息的 ID。
      - message_count: 会话中的消息总数。
      - last_message_at: 最后一条消息的时间戳。
      - context_filters: 上下文过滤器（JSON 字段，存储如 dataset_id 等过滤条件）。
      - created_at / updated_at: 创建/更新时间（auto_now_add / auto_now）。
    """

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
    """
    聊天消息实体。

    类比 SpringBoot：
      - 相当于 JPA Entity，映射到 chat_message 表。
      - 每条记录代表会话中的一条用户或助手消息。

    字段：
      - session: 所属会话（外键 -> ChatSession）。
      - sequence: 消息序号（在会话内自增，类似排序字段）。
      - role: 消息角色（user/assistant/system），类比 ChatGPT 的消息角色。
      - message_type: 消息类型（目前仅 text）。
      - status: 消息状态（pending/complete/failed）。
      - citations_json: 引用列表（JSON 字段），存储回答引用的知识库资料。
      - model_metadata_json: 模型元数据（JSON 字段），存储 answer_mode 等标识。
      - client_message_id: 客户端消息 ID（用于前端去重/追踪）。
      - content: 消息正文内容。
      - created_at / updated_at: 创建/更新时间。

    save() 方法：
      - 覆盖了 Django Model 的 save()，在 sequence 为空时自动计算下一个序号。
      - 类比 JPA 中的 @PrePersist 回调。
    """

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
        """
        保存消息时自动计算消息序号（sequence）。

        如果 sequence 为空，自动取当前会话中最大 sequence + 1。
        类比 JPA 的 @PrePersist 生命周期回调。
        """
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
    """
    长期记忆条目实体。

    类比 SpringBoot：
      - 相当于 JPA Entity，映射到 memory_item 表。
      - 存储用户的知识偏好、项目背景、确认事实、工作规则等长期记忆。

    字段：
      - user: 所属用户（外键 -> AUTH_USER_MODEL）。
      - scope_type: 作用域类型（user_global 个人全局 / project 项目 / dataset 数据集）。
      - scope_key: 作用域键值（如 dataset_id），配合 scope_type 定位上下文。
      - memory_type: 记忆类型（user_preference / project_background / confirmed_fact / work_rule）。
      - title: 记忆标题。
      - content: 记忆内容正文。
      - confidence_score: 置信度评分（0.00 ~ 1.00），表示该记忆的可信程度。
      - source_kind: 来源方式（auto 自动提取 / manual 手动添加）。
      - status: 状态（active 激活 / archived 归档 / deleted 已删除）。
      - pinned: 是否置顶。
      - fingerprint: 内容指纹（SHA256 哈希），用于去重。
      - embedding: 文本向量（JSON 数组），用于语义搜索。
      - last_verified_at: 最后验证时间。
      - created_at / updated_at: 创建/更新时间。
    """

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
    embedding = models.JSONField(default=list, blank=True)
    last_verified_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-pinned", "-updated_at", "-id"]


class MemoryEvidence(models.Model):
    """
    记忆证据实体。

    类比 SpringBoot：
      - 相当于 JPA Entity，映射到 memory_evidence 表。
      - 将记忆条目与产生它的会话/消息关联，并记录证据摘要。

    字段：
      - memory_item: 关联的记忆条目（外键 -> MemoryItem）。
      - session: 来源会话（可为空）。
      - message: 来源消息（可为空）。
      - evidence_excerpt: 证据摘要（截取自原文的关键片段）。
      - extractor_version: 提取器版本标识。
      - confirmation_status: 确认状态（pending / confirmed / rejected）。
      - created_at: 创建时间。

    约束：
      - CheckConstraint: 要求 session 和 message 至少有一个不为空，确保每条证据都有来源。
    """

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
    """
    记忆操作审计日志实体。

    类比 SpringBoot：
      - 相当于 JPA Entity，映射到 memory_action_log 表。
      - 记录用户对记忆条目的所有操作（查看、删除、置顶、手动添加/编辑等），用于审计追溯。

    字段：
      - memory_item: 操作的记忆条目（外键 -> MemoryItem）。
      - actor_user: 执行操作的用户（外键 -> AUTH_USER_MODEL）。
      - action: 操作类型（view / delete / pin / unpin / manual_add / manual_edit）。
      - details_json: 操作详情（JSON 字段，如置顶操作记录 pinned=true/false）。
      - created_at: 操作发生时间。
    """

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
