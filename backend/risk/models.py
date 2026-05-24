"""
Risk 数据模型定义。
类比 SpringBoot: 相当于 JPA 的 @Entity 实体类，定义数据库表结构和字段映射。

定义了三个核心模型:
- RiskEvent:          风险事件（LLM 从文档中提取的风险信号）
- RiskReport:         风险报告（汇总生成的分析报告）
- RiskExtractionTask: 风险提取任务（管理异步提取的状态和进度）
"""

import uuid

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from knowledgebase.models import Document, DocumentChunk


class RiskEvent(models.Model):
    """风险事件模型 —— LLM 从文档中提取的风险信号。

    类比 SpringBoot: 相当于一个 JPA @Entity 类，映射到 risk_event 表。
    每条记录代表从金融文档中识别到的一个风险事件（如流动性风险、信用风险等）。

    生命周期:
    - pending:    待审核（默认状态，需要管理员审核）
    - approved:   已通过（被认可的风险事件，可用于生成报告）
    - rejected:   已驳回（被否定的风险事件）
    """

    # ---- 风险级别常量 ----
    LEVEL_LOW = "low"          # 低风险
    LEVEL_MEDIUM = "medium"    # 中风险
    LEVEL_HIGH = "high"        # 高风险
    LEVEL_CRITICAL = "critical"  # 严重风险
    LEVEL_CHOICES = (
        (LEVEL_LOW, "Low"),
        (LEVEL_MEDIUM, "Medium"),
        (LEVEL_HIGH, "High"),
        (LEVEL_CRITICAL, "Critical"),
    )

    # ---- 审核状态常量 ----
    STATUS_PENDING = "pending"      # 待审核
    STATUS_APPROVED = "approved"    # 已通过
    STATUS_REJECTED = "rejected"    # 已驳回
    STATUS_CHOICES = (
        (STATUS_PENDING, "Pending"),
        (STATUS_APPROVED, "Approved"),
        (STATUS_REJECTED, "Rejected"),
    )

    # 公司名称
    company_name = models.CharField(max_length=255, db_index=True)
    # 风险类型（liquidity, credit, market, compliance, operation, litigation, governance, other）
    risk_type = models.CharField(max_length=128, db_index=True)
    # 风险级别
    risk_level = models.CharField(
        max_length=32,
        choices=LEVEL_CHOICES,
        default=LEVEL_MEDIUM,
        db_index=True,
    )
    # 事件发生时间（来自原始文档）
    event_time = models.DateTimeField(blank=True, null=True, db_index=True)
    # 风险摘要（LLM 生成的一句话概括）
    summary = models.TextField()
    # 证据文本（LLM 出具的引用原文证据）
    evidence_text = models.TextField()
    # 置信度分数 [0.0, 1.0]
    confidence_score = models.DecimalField(
        max_digits=4,
        decimal_places=3,
        validators=[MinValueValidator(0), MaxValueValidator(1)],
    )
    # 审核状态
    review_status = models.CharField(
        max_length=32,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
        db_index=True,
    )
    # 来源文档
    document = models.ForeignKey(
        Document,
        related_name="risk_events",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
    )
    # 来源文档块
    chunk = models.ForeignKey(
        DocumentChunk,
        related_name="risk_events",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
    )
    # 扩展元数据（包含 materiality_score, likelihood_score, citations, watchpoints 等增强信息）
    metadata = models.JSONField(default=dict, blank=True)
    # 创建时间
    created_at = models.DateTimeField(auto_now_add=True)
    # 最后更新时间
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        """模型元数据配置。"""
        # 按创建时间倒序排列
        ordering = ["-created_at", "-id"]


class RiskReport(models.Model):
    """风险报告模型 —— 基于风险事件汇总生成的报告。

    类比 SpringBoot: 相当于一个 JPA @Entity 类，映射到 risk_report 表。
    支持三种报告范围:
    - company:    公司维度
    - document:   文档维度
    - time_range: 时间区间维度
    """

    # ---- 报告范围常量 ----
    SCOPE_COMPANY = "company"        # 公司维度报告
    SCOPE_DOCUMENT = "document"      # 单文档维度报告
    SCOPE_TIME_RANGE = "time_range"  # 时间区间维度报告
    SCOPE_CHOICES = (
        (SCOPE_COMPANY, "Company"),
        (SCOPE_DOCUMENT, "Document"),
        (SCOPE_TIME_RANGE, "Time Range"),
    )

    # 报告范围类型
    scope_type = models.CharField(
        max_length=32,
        choices=SCOPE_CHOICES,
        db_index=True,
    )
    # 报告标题
    title = models.CharField(max_length=255)
    # 公司名称（公司报告特有）
    company_name = models.CharField(max_length=255, blank=True, null=True, db_index=True)
    # 时间区间起点
    period_start = models.DateField(blank=True, null=True, db_index=True)
    # 时间区间终点
    period_end = models.DateField(blank=True, null=True, db_index=True)
    # 报告摘要
    summary = models.TextField(blank=True)
    # 报告正文（Markdown 格式）
    content = models.TextField()
    # 源数据元信息（事件 ID 列表、分布统计等）
    source_metadata = models.JSONField(default=dict, blank=True)
    # 创建时间
    created_at = models.DateTimeField(auto_now_add=True)
    # 最后更新时间
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        """模型元数据配置。"""
        ordering = ["-created_at", "-id"]


class RiskExtractionTask(models.Model):
    """风险提取任务模型 —— 追踪异步风险提取任务的状态和进度。

    类比 SpringBoot: 相当于一个异步任务的状态追踪实体。
    每个任务对应一个文档的风险提取过程，记录从排队到完成的完整状态。

    状态流转:
    queued -> running -> succeeded / failed

    步骤流转:
    queued -> retrieving -> extracting_signals -> adjudicating
           -> routing_review -> extracting -> verifying -> persisting -> completed
    """

    # ---- 错误类型常量 ----
    ERROR_BUSY = "risk_extraction_busy"              # 队列繁忙
    ERROR_TIMEOUT = "risk_extraction_timeout"         # 通用超时
    ERROR_QUEUE_TIMEOUT = "risk_extraction_queue_timeout"  # 排队超时
    ERROR_STAGE_TIMEOUT = "risk_extraction_stage_timeout"  # 阶段超时
    ERROR_TASK_MISSING = "risk_extraction_task_missing"    # 任务丢失

    # ---- 任务状态常量 ----
    STATUS_QUEUED = "queued"          # 排队中
    STATUS_RUNNING = "running"         # 执行中
    STATUS_SUCCEEDED = "succeeded"     # 已完成
    STATUS_FAILED = "failed"           # 已失败
    STATUS_CHOICES = (
        (STATUS_QUEUED, "Queued"),
        (STATUS_RUNNING, "Running"),
        (STATUS_SUCCEEDED, "Succeeded"),
        (STATUS_FAILED, "Failed"),
    )

    # ---- 执行步骤常量 ----
    STEP_QUEUED = "queued"                    # 排队中
    STEP_RETRIEVING = "retrieving"            # 检索相关切块
    STEP_EXTRACTING_SIGNALS = "extracting_signals"  # 提取风险信号
    STEP_ADJUDICATING = "adjudicating"        # 风险判读
    STEP_ROUTING_REVIEW = "routing_review"    # 人工复核分流
    STEP_EXTRACTING = "extracting"            # 抽取
    STEP_VERIFYING = "verifying"              # 验证
    STEP_PERSISTING = "persisting"            # 持久化
    STEP_COMPLETED = "completed"              # 已完成
    STEP_FAILED = "failed"                    # 已失败
    STEP_CHOICES = (
        (STEP_QUEUED, "Queued"),
        (STEP_RETRIEVING, "Retrieving"),
        (STEP_EXTRACTING_SIGNALS, "Extracting signals"),
        (STEP_ADJUDICATING, "Adjudicating"),
        (STEP_ROUTING_REVIEW, "Routing review"),
        (STEP_EXTRACTING, "Extracting"),
        (STEP_VERIFYING, "Verifying"),
        (STEP_PERSISTING, "Persisting"),
        (STEP_COMPLETED, "Completed"),
        (STEP_FAILED, "Failed"),
    )

    # 任务 ID（UUID 主键）
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # 关联的文档
    document = models.ForeignKey(
        Document,
        related_name="risk_extraction_tasks",
        on_delete=models.CASCADE,
    )
    # Celery 异步任务的 ID
    celery_task_id = models.CharField(max_length=255, blank=True, db_index=True)
    # 任务状态
    status = models.CharField(
        max_length=32,
        choices=STATUS_CHOICES,
        default=STATUS_QUEUED,
    )
    # 当前执行步骤
    current_step = models.CharField(
        max_length=32,
        choices=STEP_CHOICES,
        default=STEP_QUEUED,
    )
    # 进度百分比 [0-100]
    progress = models.PositiveSmallIntegerField(default=6)
    # 创建的风险事件数量
    created_count = models.PositiveIntegerField(default=0)
    # 状态消息
    message = models.TextField(blank=True)
    # 错误信息
    error_message = models.TextField(blank=True)
    # 结果数据
    result_payload = models.JSONField(default=dict, blank=True)
    # 开始执行时间
    started_at = models.DateTimeField(blank=True, null=True)
    # 完成时间
    finished_at = models.DateTimeField(blank=True, null=True)
    # 创建时间
    created_at = models.DateTimeField(auto_now_add=True)
    # 最后更新时间
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        """模型元数据配置。"""
        ordering = ["-created_at", "-updated_at"]
