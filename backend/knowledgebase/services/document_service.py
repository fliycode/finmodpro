from datetime import date
from pathlib import Path

from django.contrib.auth import get_user_model
from django.db.models import Q
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


def _parse_owner_id(raw_value):
    if raw_value in (None, ""):
        return None
    try:
        return int(raw_value)
    except (TypeError, ValueError) as exc:
        raise ValueError("owner_id 必须是整数。") from exc


def _parse_visibility(raw_value):
    if not raw_value:
        return Document.VISIBILITY_INTERNAL
    normalized = str(raw_value).strip().lower()
    valid_values = {
        Document.VISIBILITY_PRIVATE,
        Document.VISIBILITY_INTERNAL,
        Document.VISIBILITY_PUBLIC,
    }
    if normalized not in valid_values:
        raise ValueError("visibility 仅支持 private/internal/public。")
    return normalized


def _serialize_user(user):
    if user is None:
        return None
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
    }


def _is_document_admin(user):
    if user is None:
        return False
    if getattr(user, "is_superuser", False) or getattr(user, "is_staff", False):
        return True
    return user.groups.filter(name__in=["admin", "super_admin"]).exists()


def _document_access_q(user):
    if user is None:
        return Q(pk__in=[])
    if _is_document_admin(user):
        return Q()
    return (
        Q(visibility__in=[Document.VISIBILITY_INTERNAL, Document.VISIBILITY_PUBLIC])
        | Q(uploaded_by=user)
        | Q(owner=user)
    )


def get_visible_documents_queryset(user):
    return (
        Document.objects.select_related("uploaded_by", "owner")
        .prefetch_related("ingestion_tasks")
        .filter(_document_access_q(user))
        .order_by("id")
    )


def get_document_for_user(user, document_id):
    return get_visible_documents_queryset(user).get(id=document_id)


def _build_file_url(document):
    try:
        return document.file.url
    except ValueError:
        return document.file.name


def _serialize_ingestion_task(ingestion_task):
    if ingestion_task is None:
        return None
    return {
        "id": ingestion_task.id,
        "celery_task_id": ingestion_task.celery_task_id or None,
        "status": ingestion_task.status,
        "current_step": ingestion_task.current_step,
        "error_message": ingestion_task.error_message or None,
        "retry_count": ingestion_task.retry_count,
        "started_at": ingestion_task.started_at.isoformat() if ingestion_task.started_at else None,
        "finished_at": ingestion_task.finished_at.isoformat() if ingestion_task.finished_at else None,
        "created_at": ingestion_task.created_at.isoformat(),
        "updated_at": ingestion_task.updated_at.isoformat(),
    }


def _get_latest_ingestion_task(document):
    if (
        hasattr(document, "_prefetched_objects_cache")
        and "ingestion_tasks" in document._prefetched_objects_cache
    ):
        tasks = list(document._prefetched_objects_cache["ingestion_tasks"])
        return tasks[-1] if tasks else None
    return document.ingestion_tasks.order_by("id").last()


def _build_process_result(document, ingestion_task):
    if document.status == Document.STATUS_FAILED:
        return document.error_message or "文档处理失败。"
    if document.status == Document.STATUS_INDEXED:
        return "文档已完成解析、切块与索引，可用于检索。"
    if ingestion_task is None:
        return "文档已上传，等待摄取任务执行。"

    step_messages = {
        IngestionTask.STEP_QUEUED: "摄取任务已排队，等待执行。",
        IngestionTask.STEP_PARSING: "正在解析文档正文与元数据。",
        IngestionTask.STEP_CHUNKING: "正在切分文本片段。",
        IngestionTask.STEP_INDEXING: "正在写入向量索引。",
        IngestionTask.STEP_COMPLETED: "文档摄取已完成。",
        IngestionTask.STEP_FAILED: ingestion_task.error_message or document.error_message or "文档摄取失败。",
    }
    return step_messages.get(ingestion_task.current_step, "文档处理中。")


def serialize_document(document, include_content_preview=False, include_content=False):
    ingestion_task = _get_latest_ingestion_task(document)
    original_url = _build_file_url(document)

    try:
        chunk_count = document.chunks.count()
    except Exception:
        chunk_count = 0

    try:
        vector_count = document.chunks.exclude(vector_id="").count()
    except Exception:
        vector_count = 0

    parsed_text = document.parsed_text or ""

    payload = {
        "id": document.id,
        "title": document.title,
        "filename": document.filename,
        "doc_type": document.doc_type,
        "status": document.status,
        "visibility": document.visibility,
        "uploader": _serialize_user(getattr(document, "uploaded_by", None)),
        "uploaded_by": _serialize_user(getattr(document, "uploaded_by", None)),
        "owner": _serialize_user(getattr(document, "owner", None)),
        "source_date": document.source_date.isoformat() if document.source_date else None,
        "file_path": getattr(document.file, "name", ""),
        "original_url": original_url,
        "preview_url": original_url,
        "chunk_count": chunk_count,
        "vector_count": vector_count,
        "error_message": document.error_message or None,
        "process_result": _build_process_result(document, ingestion_task),
        "latest_ingestion_task": _serialize_ingestion_task(ingestion_task),
        "created_at": document.created_at.isoformat(),
        "updated_at": document.updated_at.isoformat(),
    }
    if include_content_preview:
        payload["parsed_text_preview"] = parsed_text[:200]
        payload["preview_text"] = parsed_text[:200]
    if include_content:
        payload["parsed_text"] = parsed_text
        payload["extracted_text"] = parsed_text
    return payload


def build_document_response(document, *, include_content_preview=False, message=None):
    payload = {
        "document": serialize_document(
            document,
            include_content_preview=include_content_preview,
            include_content=include_content_preview,
        )
    }
    if message is not None:
        payload["message"] = message
    return payload


def build_document_list_response(user):
    documents = list_documents(user)
    return {
        "documents": documents,
        "total": len(documents),
    }


def create_document_from_upload(
    *,
    uploaded_file,
    title,
    source_date,
    uploaded_by=None,
    owner_id=None,
    visibility=None,
):
    filename = uploaded_file.name
    doc_type = _detect_doc_type(filename)
    if doc_type not in {"txt", "pdf", "docx"}:
        raise ValueError("当前仅支持 txt/pdf/docx 文件上传。")

    owner = uploaded_by
    parsed_owner_id = _parse_owner_id(owner_id)
    if parsed_owner_id is not None:
        User = get_user_model()
        try:
            owner = User.objects.get(id=parsed_owner_id)
        except User.DoesNotExist as exc:
            raise ValueError("owner_id 对应用户不存在。") from exc

    document = Document.objects.create(
        title=title or Path(filename).stem,
        file=uploaded_file,
        filename=filename,
        doc_type=doc_type,
        uploaded_by=uploaded_by,
        owner=owner,
        visibility=_parse_visibility(visibility),
        source_date=_parse_source_date(source_date),
    )
    return document


def list_documents(user):
    return [serialize_document(document) for document in get_visible_documents_queryset(user)]


def _update_document_status(document, *, status, error_message=None):
    document.status = status
    update_fields = ["status", "updated_at"]
    if error_message is not None:
        document.error_message = error_message
        update_fields.append("error_message")
    document.save(update_fields=update_fields)


def _update_ingestion_task_step(ingestion_task, *, current_step):
    ingestion_task.current_step = current_step
    ingestion_task.save(update_fields=["current_step", "updated_at"])


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
    ingestion_task.current_step = IngestionTask.STEP_PARSING
    ingestion_task.error_message = ""
    ingestion_task.started_at = timezone.now()
    ingestion_task.finished_at = None
    ingestion_task.save(
        update_fields=[
            "status",
            "current_step",
            "error_message",
            "started_at",
            "finished_at",
            "updated_at",
        ]
    )


def _mark_ingestion_task_finished(ingestion_task, *, status, error_message=""):
    ingestion_task.status = status
    ingestion_task.current_step = (
        IngestionTask.STEP_COMPLETED
        if status == IngestionTask.STATUS_SUCCEEDED
        else IngestionTask.STEP_FAILED
    )
    ingestion_task.error_message = error_message
    ingestion_task.finished_at = timezone.now()
    ingestion_task.save(
        update_fields=[
            "status",
            "current_step",
            "error_message",
            "finished_at",
            "updated_at",
        ]
    )


def ingest_document(document, ingestion_task=None):
    try:
        parsed_text = parse_document(document)
        if ingestion_task is not None:
            _update_ingestion_task_step(
                ingestion_task,
                current_step=IngestionTask.STEP_CHUNKING,
            )
        chunk_document(document, parsed_text)
        if ingestion_task is not None:
            _update_ingestion_task_step(
                ingestion_task,
                current_step=IngestionTask.STEP_INDEXING,
            )
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

    latest_task = document.ingestion_tasks.order_by("id").last()
    if latest_task and latest_task.status in {
        IngestionTask.STATUS_QUEUED,
        IngestionTask.STATUS_RUNNING,
    }:
        return latest_task, False

    document.status = Document.STATUS_UPLOADED
    document.error_message = ""
    document.save(update_fields=["status", "error_message", "updated_at"])
    ingestion_task = IngestionTask.objects.create(
        document=document,
        status=IngestionTask.STATUS_QUEUED,
        current_step=IngestionTask.STEP_QUEUED,
    )
    async_result = ingest_document_task.delay(document.id, ingestion_task.id)
    ingestion_task.celery_task_id = async_result.id or ""
    ingestion_task.save(update_fields=["celery_task_id", "updated_at"])
    return ingestion_task, True


def start_ingestion_task(ingestion_task):
    if ingestion_task.status == IngestionTask.STATUS_FAILED:
        ingestion_task.retry_count += 1
    _mark_ingestion_task_running(ingestion_task)
    if ingestion_task.retry_count:
        ingestion_task.save(update_fields=["retry_count", "updated_at"])
    return ingestion_task
