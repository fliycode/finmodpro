from datetime import date
from pathlib import Path

from django.utils import timezone

from knowledgebase.models import Document, DocumentChunk, IngestionTask
from knowledgebase.services.chunk_service import build_document_chunks
from knowledgebase.services.parser_service import parse_document_file
from knowledgebase.services.vector_service import index_document_chunks


def _detect_doc_type(filename):
    extension = Path(filename).suffix.lower().lstrip(".")
    return extension or "unknown"


def _parse_source_date(raw_value):
    if not raw_value:
        return None
    try:
        return date.fromisoformat(raw_value)
    except ValueError as exc:
        raise ValueError("source_date 必须是 YYYY-MM-DD 格式。") from exc


def serialize_document(document, include_content_preview=False):
    payload = {
        "id": document.id,
        "title": document.title,
        "filename": document.filename,
        "doc_type": document.doc_type,
        "status": document.status,
        "source_date": document.source_date.isoformat() if document.source_date else None,
        "file_path": document.file.name,
        "chunk_count": document.chunks.count(),
        "vector_count": document.chunks.exclude(vector_id="").count(),
        "error_message": document.error_message or None,
        "created_at": document.created_at.isoformat(),
        "updated_at": document.updated_at.isoformat(),
    }
    if include_content_preview:
        payload["parsed_text_preview"] = document.parsed_text[:200]
    return payload


def build_document_response(document, *, include_content_preview=False, message=None):
    payload = {
        "document": serialize_document(
            document,
            include_content_preview=include_content_preview,
        )
    }
    if message is not None:
        payload["message"] = message
    return payload


def build_document_list_response():
    documents = list_documents()
    return {
        "documents": documents,
        "total": len(documents),
    }


def create_document_from_upload(*, uploaded_file, title, source_date):
    filename = uploaded_file.name
    doc_type = _detect_doc_type(filename)
    if doc_type not in {"txt", "pdf", "docx"}:
        raise ValueError("当前仅支持 txt/pdf/docx 文件上传。")

    document = Document.objects.create(
        title=title or Path(filename).stem,
        file=uploaded_file,
        filename=filename,
        doc_type=doc_type,
        source_date=_parse_source_date(source_date),
    )
    return document


def list_documents():
    return [serialize_document(document) for document in Document.objects.all()]


def _update_document_status(document, *, status, error_message=None):
    document.status = status
    update_fields = ["status", "updated_at"]
    if error_message is not None:
        document.error_message = error_message
        update_fields.append("error_message")
    document.save(update_fields=update_fields)


def _build_chunk_metadata(document, index):
    return {
        "document_id": document.id,
        "document_title": document.title,
        "doc_type": document.doc_type,
        "source_date": document.source_date.isoformat() if document.source_date else None,
        "chunk_index": index,
        "page_label": f"chunk-{index + 1}",
    }


def parse_document(document):
    parsed_text = parse_document_file(document)
    document.parsed_text = parsed_text
    document.error_message = ""
    document.save(update_fields=["parsed_text", "error_message", "updated_at"])
    _update_document_status(document, status=Document.STATUS_PARSED)
    return parsed_text


def chunk_document(document, parsed_text):
    DocumentChunk.objects.filter(document=document).delete()
    chunks = build_document_chunks(
        parsed_text,
        metadata_builder=lambda index: _build_chunk_metadata(document, index),
    )
    DocumentChunk.objects.bulk_create(
        [
            DocumentChunk(
                document=document,
                chunk_index=chunk["chunk_index"],
                content=chunk["content"],
                vector_id="",
                metadata=chunk["metadata"],
            )
            for chunk in chunks
        ]
    )
    _update_document_status(document, status=Document.STATUS_CHUNKED)
    return chunks


def vectorize_document(document):
    index_document_chunks(document)
    _update_document_status(document, status=Document.STATUS_INDEXED)
    return document


def _mark_ingestion_task_running(ingestion_task):
    ingestion_task.status = IngestionTask.STATUS_RUNNING
    ingestion_task.error_message = ""
    ingestion_task.started_at = timezone.now()
    ingestion_task.finished_at = None
    ingestion_task.save(
        update_fields=[
            "status",
            "error_message",
            "started_at",
            "finished_at",
            "updated_at",
        ]
    )


def _mark_ingestion_task_finished(ingestion_task, *, status, error_message=""):
    ingestion_task.status = status
    ingestion_task.error_message = error_message
    ingestion_task.finished_at = timezone.now()
    ingestion_task.save(
        update_fields=[
            "status",
            "error_message",
            "finished_at",
            "updated_at",
        ]
    )


def ingest_document(document, ingestion_task=None):
    try:
        parsed_text = parse_document(document)
        chunk_document(document, parsed_text)
        vectorize_document(document)
        if ingestion_task is not None:
            _mark_ingestion_task_finished(
                ingestion_task,
                status=IngestionTask.STATUS_SUCCEEDED,
            )
        return document
    except Exception as exc:
        DocumentChunk.objects.filter(document=document).delete()
        error_message = str(exc) or "文档摄取失败。"
        _update_document_status(
            document,
            status=Document.STATUS_FAILED,
            error_message=error_message,
        )
        if ingestion_task is not None:
            _mark_ingestion_task_finished(
                ingestion_task,
                status=IngestionTask.STATUS_FAILED,
                error_message=error_message,
            )
        raise


def enqueue_document_ingestion(document):
    from knowledgebase.tasks import ingest_document_task

    document.error_message = ""
    document.save(update_fields=["error_message", "updated_at"])
    ingestion_task = IngestionTask.objects.create(document=document)
    async_result = ingest_document_task.delay(document.id, ingestion_task.id)
    ingestion_task.celery_task_id = async_result.id or ""
    ingestion_task.save(update_fields=["celery_task_id", "updated_at"])
    return document


def start_ingestion_task(ingestion_task):
    if ingestion_task.status == IngestionTask.STATUS_FAILED:
        ingestion_task.retry_count += 1
    _mark_ingestion_task_running(ingestion_task)
    if ingestion_task.retry_count:
        ingestion_task.save(update_fields=["retry_count", "updated_at"])
    return ingestion_task
