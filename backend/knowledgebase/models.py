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
    STATUS_FAILED = "failed"
    STATUS_CHOICES = (
        (STATUS_UPLOADED, "Uploaded"),
        (STATUS_PARSED, "Parsed"),
        (STATUS_CHUNKED, "Chunked"),
        (STATUS_INDEXED, "Indexed"),
        (STATUS_FAILED, "Failed"),
    )

    title = models.CharField(max_length=255)
    file = models.FileField(upload_to="knowledgebase/documents/")
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
    STEP_CHUNKING = "chunking"
    STEP_INDEXING = "indexing"
    STEP_COMPLETED = "completed"
    STEP_FAILED = "failed"
    STEP_CHOICES = (
        (STEP_QUEUED, "Queued"),
        (STEP_PARSING, "Parsing"),
        (STEP_CHUNKING, "Chunking"),
        (STEP_INDEXING, "Indexing"),
        (STEP_COMPLETED, "Completed"),
        (STEP_FAILED, "Failed"),
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
    vector_id = models.CharField(max_length=64, blank=True, db_index=True)
    is_indexed = models.BooleanField(default=False)
    metadata = models.JSONField(default=dict, blank=True)
    start_offset = models.PositiveIntegerField(default=0)
    end_offset = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["section_index"]
        unique_together = ("document", "section_index")
