from django.conf import settings
from django.db import models


class Dataset(models.Model):
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
        ordering = ["id"]


class Document(models.Model):
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
