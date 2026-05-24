"""
知识库数据模型 (ORM Entity) 定义模块。

类比 SpringBoot: 相当于 Spring Data JPA 的 @Entity 类集合。每个 Django Model 类
映射到数据库中的一张表，Model 字段映射到表列。Django 的 Meta 内部类相当于 JPA 的
@Table、@OrderBy 等注解，提供表级元数据配置。

本模块定义了知识库的核心数据结构：数据集、文档、文档版本、摄取任务、文档分块、
文档章节分块、清洗规则和清洗结果。
"""
from django.conf import settings
from django.db import models


class Dataset(models.Model):
    """
    数据集实体 —— 文档的逻辑分组容器。

    类比 SpringBoot: 相当于一个 @Entity 类，映射到数据库中的 knowledgebase_dataset 表。
    一个 Dataset 下可包含多个 Document。

    字段:
        name:        数据集名称，必须唯一（相当于 @Column(unique=true)）
        description: 数据集描述文本
        owner:       数据集所有者，外键关联到用户模型（相当于 @ManyToOne）
        created_at:  创建时间，自动填充
        updated_at:  更新时间，自动刷新
    """
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="owned_datasets",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        """
        数据集表的元数据配置。

        类比 SpringBoot: 相当于 @Table 注解 + @OrderBy 注解，
        定义了默认排序规则为按 ID 升序。
        """
        ordering = ["id"]


class Document(models.Model):
    """
    文档实体 —— 知识库中最核心的资源单元。

    类比 SpringBoot: 相当于一个 @Entity 类，映射到 knowledgebase_document 表。
    每个文档包含上传文件信息、状态流转、可见性控制等完整生命周期管理。

    状态机流转: uploaded -> parsed -> cleaning -> chunked -> indexed
    失败时进入 failed 状态。

    字段:
        title:         文档标题
        file:          上传的文件本体（相当于 Spring 的 @Lob + MultipartFile 存储）
        file_size:     文件大小（字节）
        file_hash:     文件 SHA256 哈希值，用于去重校验
        filename:      原始文件名
        doc_type:      文档类型（如 pdf、docx、txt）
        uploaded_by:   上传者，外键关联用户
        owner:         所有者，外键关联用户
        dataset:       所属数据集，外键关联 Dataset
        visibility:    可见性等级 (private/internal/public)
        status:        当前处理状态
        source_date:   文档来源日期
        parsed_text:   解析后的纯文本内容
        error_message: 错误信息（处理失败时填充）
        created_at:    创建时间
        updated_at:    更新时间
    """
    VISIBILITY_PRIVATE = "private"
    VISIBILITY_INTERNAL = "internal"
    VISIBILITY_PUBLIC = "public"
    VISIBILITY_CHOICES = (
        (VISIBILITY_PRIVATE, "Private"),
        (VISIBILITY_INTERNAL, "Internal"),
        (VISIBILITY_PUBLIC, "Public"),
    )

    STATUS_UPLOADED = "uploaded"
    STATUS_PARSED = "parsed"
    STATUS_CHUNKED = "chunked"
    STATUS_INDEXED = "indexed"
    STATUS_CLEANING = "cleaning"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = (
        (STATUS_UPLOADED, "Uploaded"),
        (STATUS_PARSED, "Parsed"),
        (STATUS_CLEANING, "Cleaning"),
        (STATUS_CHUNKED, "Chunked"),
        (STATUS_INDEXED, "Indexed"),
        (STATUS_FAILED, "Failed"),
    )

    title = models.CharField(max_length=255)
    file = models.FileField(upload_to="knowledgebase/documents/")
    file_size = models.PositiveBigIntegerField(default=0, help_text="File size in bytes")
    file_hash = models.CharField(max_length=64, blank=True, default="", db_index=True, help_text="SHA256 hash of the file content")
    filename = models.CharField(max_length=255)
    doc_type = models.CharField(max_length=32)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="uploaded_documents",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="owned_documents",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
    )
    dataset = models.ForeignKey(
        Dataset,
        related_name="documents",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
    )
    visibility = models.CharField(
        max_length=32,
        choices=VISIBILITY_CHOICES,
        default=VISIBILITY_INTERNAL,
    )
    status = models.CharField(
        max_length=32,
        choices=STATUS_CHOICES,
        default=STATUS_UPLOADED,
    )
    source_date = models.DateField(blank=True, null=True)
    parsed_text = models.TextField(blank=True)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["id"]


class DocumentVersion(models.Model):
    """
    文档版本实体 —— 追踪同一根文档的多个版本。

    类比 SpringBoot: 相当于 @Entity 表，记录文档的版本历史。
    每个版本指向一个独立的 Document 实例 (OneToOneField)，
    并通过 root_document 关联到原始根文档。

    字段:
        root_document:    根文档（第一个版本），外键关联 Document
        document:         当前版本的文档实例，一对一关联 Document
        version_number:   版本序号（从 1 开始递增）
        is_current:       是否为当前最新版本
        source_type:      来源类型（如 upload、api、email）
        source_label:     来源标签（人类可读的来源描述）
        source_metadata:  来源元数据（JSON 格式，灵活扩展）
        processing_notes: 处理备注
        created_at:       版本创建时间
    """
    root_document = models.ForeignKey(
        Document,
        related_name="versions",
        on_delete=models.CASCADE,
    )
    document = models.OneToOneField(
        Document,
        related_name="version_record",
        on_delete=models.CASCADE,
    )
    version_number = models.PositiveIntegerField()
    is_current = models.BooleanField(default=True)
    source_type = models.CharField(max_length=64, blank=True, default="")
    source_label = models.CharField(max_length=255, blank=True, default="")
    source_metadata = models.JSONField(default=dict, blank=True)
    processing_notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-version_number", "-id"]
        unique_together = (
            ("root_document", "version_number"),
        )


class IngestionTask(models.Model):
    """
    文档摄取任务实体 —— 追踪文档从上传到索引的全流程。

    类比 SpringBoot: 相当于一个异步任务追踪表，类似 Spring Batch 的 JobExecution 表。
    每个任务记录文档处理管线的每一步状态：解析 -> 清洗 -> 分块 -> 索引 -> 图谱同步。

    字段:
        document:                 关联的文档
        celery_task_id:           Celery 异步任务 ID（相当于 @Async 返回的 Future ID）
        status:                   任务整体状态 (queued/running/succeeded/failed)
        current_step:             当前执行步骤
        strategy:                 分块策略 (flat 扁平 / hierarchical 层级)
        graph_sync_status:        知识图谱同步状态
        graph_sync_error_message: 图谱同步错误信息
        graph_sync_started_at:    图谱同步开始时间
        graph_sync_finished_at:   图谱同步结束时间
        graph_document_id:        图谱中的文档 ID
        graph_track_id:           图谱追踪 ID
        total_section_count:      总章节数
        indexed_section_count:    已索引章节数
        failed_section_count:     失败章节数
        error_message:            错误信息
        started_at:               任务开始时间
        finished_at:              任务完成时间
        retry_count:              重试次数
        created_at:               创建时间
        updated_at:               更新时间
    """
    STATUS_QUEUED = "queued"
    STATUS_RUNNING = "running"
    STATUS_SUCCEEDED = "succeeded"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = (
        (STATUS_QUEUED, "Queued"),
        (STATUS_RUNNING, "Running"),
        (STATUS_SUCCEEDED, "Succeeded"),
        (STATUS_FAILED, "Failed"),
    )
    STEP_QUEUED = "queued"
    STEP_PARSING = "parsing"
    STEP_CLEANING = "cleaning"
    STEP_CHUNKING = "chunking"
    STEP_INDEXING = "indexing"
    STEP_GRAPH_SYNC = "graph_sync"
    STEP_COMPLETED = "completed"
    STEP_FAILED = "failed"
    STEP_CHOICES = (
        (STEP_QUEUED, "Queued"),
        (STEP_PARSING, "Parsing"),
        (STEP_CLEANING, "Cleaning"),
        (STEP_CHUNKING, "Chunking"),
        (STEP_INDEXING, "Indexing"),
        (STEP_GRAPH_SYNC, "Graph sync"),
        (STEP_COMPLETED, "Completed"),
        (STEP_FAILED, "Failed"),
    )
    GRAPH_SYNC_STATUS_PENDING = "pending"
    GRAPH_SYNC_STATUS_RUNNING = "running"
    GRAPH_SYNC_STATUS_SUCCEEDED = "succeeded"
    GRAPH_SYNC_STATUS_FAILED = "failed"
    GRAPH_SYNC_STATUS_SKIPPED = "skipped"
    GRAPH_SYNC_STATUS_CHOICES = (
        (GRAPH_SYNC_STATUS_PENDING, "Pending"),
        (GRAPH_SYNC_STATUS_RUNNING, "Running"),
        (GRAPH_SYNC_STATUS_SUCCEEDED, "Succeeded"),
        (GRAPH_SYNC_STATUS_FAILED, "Failed"),
        (GRAPH_SYNC_STATUS_SKIPPED, "Skipped"),
    )
    STRATEGY_FLAT = "flat"
    STRATEGY_HIERARCHICAL = "hierarchical"
    STRATEGY_CHOICES = (
        (STRATEGY_FLAT, "Flat"),
        (STRATEGY_HIERARCHICAL, "Hierarchical"),
    )

    document = models.ForeignKey(
        Document,
        related_name="ingestion_tasks",
        on_delete=models.CASCADE,
    )
    celery_task_id = models.CharField(max_length=255, blank=True, db_index=True)
    status = models.CharField(
        max_length=32,
        choices=STATUS_CHOICES,
        default=STATUS_QUEUED,
    )
    current_step = models.CharField(
        max_length=32,
        choices=STEP_CHOICES,
        default=STEP_QUEUED,
    )
    strategy = models.CharField(
        max_length=32,
        choices=STRATEGY_CHOICES,
        default=STRATEGY_FLAT,
    )
    graph_sync_status = models.CharField(
        max_length=32,
        choices=GRAPH_SYNC_STATUS_CHOICES,
        default=GRAPH_SYNC_STATUS_PENDING,
    )
    graph_sync_error_message = models.TextField(blank=True)
    graph_sync_started_at = models.DateTimeField(blank=True, null=True)
    graph_sync_finished_at = models.DateTimeField(blank=True, null=True)
    graph_document_id = models.CharField(max_length=255, blank=True, db_index=True)
    graph_track_id = models.CharField(max_length=255, blank=True, db_index=True)
    total_section_count = models.PositiveIntegerField(default=0)
    indexed_section_count = models.PositiveIntegerField(default=0)
    failed_section_count = models.PositiveIntegerField(default=0)
    error_message = models.TextField(blank=True)
    started_at = models.DateTimeField(blank=True, null=True)
    finished_at = models.DateTimeField(blank=True, null=True)
    retry_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["id"]


class DocumentChunk(models.Model):
    """
    文档分块实体 —— 文档被切分后的最小检索单元。

    类比 SpringBoot: 相当于 @Entity 表，存储文档的分块内容。
    每个 chunk 对应 Milvus/向量数据库中的一个向量条目，用于 RAG 检索。

    字段:
        document:      所属文档
        section_chunk: 所属章节分块（层级策略下使用）
        chunk_index:   分块序号（在文档内的顺序）
        content:       分块的原始文本内容
        search_text:   用于检索的预处理文本
        vector_id:     向量数据库中对应的向量 ID
        metadata:      分块元数据（JSON 格式，如页码、位置等）
        created_at:    创建时间
    """
    document = models.ForeignKey(
        Document,
        related_name="chunks",
        on_delete=models.CASCADE,
    )
    section_chunk = models.ForeignKey(
        "DocumentSectionChunk",
        related_name="child_chunks",
        on_delete=models.CASCADE,
        blank=True,
        null=True,
    )
    chunk_index = models.PositiveIntegerField()
    content = models.TextField()
    search_text = models.TextField(blank=True, default="")
    vector_id = models.CharField(max_length=64, blank=True, db_index=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["chunk_index"]
        unique_together = ("document", "chunk_index")


class DocumentSectionChunk(models.Model):
    """
    文档章节分块实体 —— 层级策略下的章节级分块。

    类比 SpringBoot: 相当于 @Entity 表，在 hierarchical 策略下，
    文档先分为 SectionChunk（章节级），再细分为 DocumentChunk（段落级）。

    字段:
        document:      所属文档
        section_index: 章节序号
        section_label: 章节标签/标题
        section_path:  章节路径（如 "1 > 1.1 > 1.1.1"）
        content:       章节文本内容
        search_text:   用于检索的预处理文本
        vector_id:     向量数据库中的向量 ID
        is_indexed:    是否已索引到向量数据库
        metadata:      章节元数据
        start_offset:  在原文中的起始偏移量
        end_offset:    在原文中的结束偏移量
        created_at:    创建时间
    """
    document = models.ForeignKey(
        Document,
        related_name="section_chunks",
        on_delete=models.CASCADE,
    )
    section_index = models.PositiveIntegerField()
    section_label = models.CharField(max_length=255, blank=True, default="")
    section_path = models.CharField(max_length=512, blank=True, default="")
    content = models.TextField()
    search_text = models.TextField(blank=True, default="")
    vector_id = models.CharField(max_length=64, blank=True, db_index=True)
    is_indexed = models.BooleanField(default=False)
    metadata = models.JSONField(default=dict, blank=True)
    start_offset = models.PositiveIntegerField(default=0)
    end_offset = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["section_index"]
        unique_together = ("document", "section_index")


class CleaningRule(models.Model):
    """
    清洗规则实体 —— 定义文本清洗的一条规则。

    类比 SpringBoot: 相当于 @Entity 表，存储可配置的数据清洗规则。
    每类规则执行特定的文本清洗操作（去空格、修复编码、去重等）。

    字段:
        name:       规则名称，唯一
        rule_type:  规则类型（如 clean_whitespace、dedup_exact）
        config:     规则配置参数（JSON 格式，灵活扩展）
        enabled:    是否启用
        priority:   执行优先级（数值越小优先级越高）
        created_by: 创建者，外键关联用户
        created_at: 创建时间
        updated_at: 更新时间
    """
    RULE_TYPE_CHOICES = (
        ("clean_whitespace", "Clean whitespace"),
        ("fix_encoding", "Fix encoding"),
        ("normalize_quotes", "Normalize quotes"),
        ("remove_bullets", "Remove bullets"),
        ("group_broken_paragraphs", "Group broken paragraphs"),
        ("remove_header_footer", "Remove header/footer"),
        ("remove_page_numbers", "Remove page numbers"),
        ("remove_boilerplate", "Remove boilerplate"),
        ("remove_urls_emails", "Remove URLs and emails"),
        ("dedup_exact", "Deduplicate exact"),
        ("dedup_near", "Deduplicate near"),
        ("fix_ocr_artifacts", "Fix OCR artifacts"),
        ("normalize_financial_numbers", "Normalize financial numbers"),
    )

    name = models.CharField(max_length=255, unique=True)
    rule_type = models.CharField(max_length=64, choices=RULE_TYPE_CHOICES, db_index=True)
    config = models.JSONField(default=dict, blank=True)
    enabled = models.BooleanField(default=True)
    priority = models.PositiveIntegerField(default=100)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="created_cleaning_rules",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["priority", "id"]


class DocumentCleaningResult(models.Model):
    """
    文档清洗结果实体 —— 记录每次清洗操作的输出。

    类比 SpringBoot: 相当于 @Entity 表，记录清洗作业的执行结果和质检数据。
    每次对文档执行清洗后生成一条结果记录。

    字段:
        document:         被清洗的文档
        rules_applied:    实际应用的规则列表（JSON 数组）
        issues_found:     发现的问题列表（JSON 数组）
        quality_score:    清洗后的质量评分 (0.0 ~ 1.0)
        quality_signals:  质量信号详情（JSON 格式）
        original_length:  清洗前文本长度
        cleaned_length:   清洗后文本长度
        dedup_count:      去重条数
        cleaned_at:       清洗执行时间
    """
    document = models.ForeignKey(
        Document,
        related_name="cleaning_results",
        on_delete=models.CASCADE,
    )
    rules_applied = models.JSONField(default=list, blank=True)
    issues_found = models.JSONField(default=list, blank=True)
    quality_score = models.FloatField(default=0.0)
    quality_signals = models.JSONField(default=dict, blank=True)
    original_length = models.PositiveIntegerField(default=0)
    cleaned_length = models.PositiveIntegerField(default=0)
    dedup_count = models.PositiveIntegerField(default=0)
    cleaned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-cleaned_at", "-id"]
