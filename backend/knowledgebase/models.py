from django.db import models


class Document(models.Model):
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


class DocumentChunk(models.Model):
    document = models.ForeignKey(
        Document,
        related_name="chunks",
        on_delete=models.CASCADE,
    )
    chunk_index = models.PositiveIntegerField()
    content = models.TextField()
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["chunk_index"]
        unique_together = ("document", "chunk_index")
