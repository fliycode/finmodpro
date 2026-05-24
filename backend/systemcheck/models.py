"""
Systemcheck 数据模型 —— 定义审计日志实体。

类比 SpringBoot: 相当于 JPA @Entity 类，用于记录系统操作的审计追踪信息。
审计日志类似于 Spring Data Audit 或 Envers 的自动审计记录，
记录谁 (actor) 在何时执行了什么操作 (action) 以及结果 (status)。
"""

from django.conf import settings
from django.db import models


class AuditRecord(models.Model):
    """
    审计记录实体 —— 记录系统关键操作的审计日志。

    类比 SpringBoot: 相当于 JPA @Entity + @EntityListeners(AuditingEntityListener.class)，
    但采用显式记录而非自动拦截的方式，记录用户操作的完整信息。

    状态常量含义:
        submitted = 已提交（操作已发起但未完成）
        succeeded = 已成功（操作执行成功）
        failed    = 已失败（操作执行失败）
        retried   = 重试中（操作正在重新执行）
        skipped   = 已跳过（操作被跳过，如发现重复任务）
    """
    # 操作状态常量
    STATUS_SUBMITTED = "submitted"
    STATUS_SUCCEEDED = "succeeded"
    STATUS_FAILED = "failed"
    STATUS_RETRIED = "retried"
    STATUS_SKIPPED = "skipped"
    STATUS_CHOICES = (
        (STATUS_SUBMITTED, "Submitted"),
        (STATUS_SUCCEEDED, "Succeeded"),
        (STATUS_FAILED, "Failed"),
        (STATUS_RETRIED, "Retried"),
        (STATUS_SKIPPED, "Skipped"),
    )

    # 操作者外键 —— 执行操作的用户，用户删除时 SET NULL
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="audit_records",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
    )
    # 操作名称 —— 如 "risk.extract", "knowledgebase.ingest" (类似 Spring AOP 中的方法全限定名)
    action = models.CharField(max_length=128, db_index=True)
    # 操作目标类型 —— 如 "document", "risk_event"
    target_type = models.CharField(max_length=64, db_index=True)
    # 操作目标 ID —— 被操作实体的主键
    target_id = models.CharField(max_length=64, blank=True, default="", db_index=True)
    # 操作状态
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, db_index=True)
    # 详细信息 —— JSON 字段存储操作附加上下文 (如 task_id, error 信息)
    detail_payload = models.JSONField(default=dict, blank=True)
    # 创建时间
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        """按创建时间降序排列，最新记录在前。"""
        ordering = ["-created_at", "-id"]
