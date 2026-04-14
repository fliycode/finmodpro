import logging
from datetime import date
from datetime import timedelta
from math import ceil
from pathlib import Path

from django.contrib.auth import get_user_model
from django.conf import settings
from django.db import DatabaseError, OperationalError, ProgrammingError, transaction
from django.db.models import Q
from django.utils import timezone

from knowledgebase.models import Dataset, Document, DocumentChunk, DocumentVersion, IngestionTask
from knowledgebase.services.chunk_service import build_document_chunks
from knowledgebase.services.parser_service import parse_document_file
from knowledgebase.services.vector_service import VectorService, index_document_chunks

logger = logging.getLogger(__name__)


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


def _parse_dataset_id(raw_value):
    if raw_value in (None, "", "all"):
        return None
    try:
        return int(raw_value)
    except (TypeError, ValueError) as exc:
        raise ValueError("dataset_id 必须是整数。") from exc


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


def _serialize_dataset_summary(dataset):
    if dataset is None:
        return None
    return {
        "id": dataset.id,
        "name": dataset.name,
    }


def _get_version_record(document):
    if document is None:
        return None

    try:
        return document.version_record
    except DocumentVersion.DoesNotExist:
        return None


def _serialize_provenance(version_record):
    if version_record is None:
        return {
            "source_type": "upload",
            "source_label": "",
            "source_metadata": {},
            "processing_notes": "",
        }

    return {
        "source_type": version_record.source_type or "upload",
        "source_label": version_record.source_label or "",
        "source_metadata": version_record.source_metadata or {},
        "processing_notes": version_record.processing_notes or "",
    }


def _get_root_document_id(document, version_record):
    if version_record is None:
        return document.id
    return version_record.root_document_id


def _get_current_version_number(document, version_record):
    if version_record is None:
        return 1
    return version_record.version_number


def _get_version_count(document, version_record):
    if version_record is None:
        return 1

    root_document = getattr(version_record, "root_document", None)
    annotated_count = getattr(root_document, "version_count", None)
    if annotated_count is not None:
        return annotated_count
    return DocumentVersion.objects.filter(root_document_id=version_record.root_document_id).count()


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
        Document.objects.select_related(
            "uploaded_by",
            "owner",
            "dataset",
            "version_record",
            "version_record__root_document",
        )
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
    version_record = _get_version_record(document)
    provenance = _serialize_provenance(version_record)

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
        "dataset": _serialize_dataset_summary(getattr(document, "dataset", None)),
        "uploader": _serialize_user(getattr(document, "uploaded_by", None)),
        "uploaded_by": _serialize_user(getattr(document, "uploaded_by", None)),
        "owner": _serialize_user(getattr(document, "owner", None)),
        "source_date": document.source_date.isoformat() if document.source_date else None,
        "root_document_id": _get_root_document_id(document, version_record),
        "version_number": _get_current_version_number(document, version_record),
        "current_version": _get_current_version_number(document, version_record),
        "version_count": _get_version_count(document, version_record),
        "is_current_version": version_record.is_current if version_record is not None else True,
        "provenance": provenance,
        "source_type": provenance["source_type"],
        "source_label": provenance["source_label"],
        "source_metadata": provenance["source_metadata"],
        "processing_notes": provenance["processing_notes"],
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


def _normalize_page(value, default=1):
    try:
        return max(int(value), 1)
    except (TypeError, ValueError):
        return default


def _normalize_page_size(value, default=10, max_page_size=50):
    try:
        return min(max(int(value), 1), max_page_size)
    except (TypeError, ValueError):
        return default


def _filter_documents(queryset, *, q="", status="all", time_range="all", dataset_id=None):
    keyword = (q or "").strip()
    if keyword:
        queryset = queryset.filter(
            Q(title__icontains=keyword)
            | Q(filename__icontains=keyword)
            | Q(uploaded_by__username__icontains=keyword)
            | Q(uploaded_by__email__icontains=keyword)
            | Q(parsed_text__icontains=keyword)
        )

    normalized_status = str(status or "all").lower()
    if normalized_status == "indexed":
        queryset = queryset.filter(status=Document.STATUS_INDEXED)
    elif normalized_status == "failed":
        queryset = queryset.filter(status=Document.STATUS_FAILED)
    elif normalized_status == "processing":
        queryset = queryset.filter(
            Q(status__in=[Document.STATUS_PARSED, Document.STATUS_CHUNKED])
            | Q(
                ingestion_tasks__status__in=[
                    IngestionTask.STATUS_QUEUED,
                    IngestionTask.STATUS_RUNNING,
                ]
            )
        ).distinct()

    normalized_time_range = str(time_range or "all").lower()
    if normalized_time_range in {"7d", "30d"}:
        days = 7 if normalized_time_range == "7d" else 30
        cutoff = timezone.now() - timedelta(days=days)
        queryset = queryset.filter(created_at__gte=cutoff)

    parsed_dataset_id = _parse_dataset_id(dataset_id)
    if parsed_dataset_id is not None:
        queryset = queryset.filter(dataset_id=parsed_dataset_id)

    return queryset


def build_document_list_response(
    user, *, q="", status="all", time_range="all", dataset_id=None, page=None, page_size=None
):
    queryset = _filter_documents(
        get_visible_documents_queryset(user),
        q=q,
        status=status,
        time_range=time_range,
        dataset_id=dataset_id,
    )
    queryset = queryset.filter(
        Q(version_record__is_current=True) | Q(version_record__isnull=True)
    )
    total = queryset.count()
    if page is None and page_size is None:
        return {
            "documents": [serialize_document(document) for document in queryset],
            "total": total,
        }

    safe_page_size = _normalize_page_size(page_size)
    safe_page = _normalize_page(page)
    total_pages = ceil(total / safe_page_size) if total else 0
    start = (safe_page - 1) * safe_page_size
    stop = start + safe_page_size
    documents = [serialize_document(document) for document in queryset[start:stop]]
    return {
        "documents": documents,
        "total": total,
        "page": safe_page,
        "page_size": safe_page_size,
        "total_pages": total_pages,
    }


def serialize_chunk(chunk):
    metadata = chunk.metadata or {}
    return {
        "id": chunk.id,
        "chunk_index": chunk.chunk_index,
        "content": chunk.content,
        "vector_id": chunk.vector_id or "",
        "page_label": metadata.get("page_label", f"chunk-{chunk.chunk_index + 1}"),
        "metadata": metadata,
        "created_at": chunk.created_at.isoformat(),
    }


def build_document_chunks_response(document):
    return {
        "document_id": document.id,
        "chunks": [serialize_chunk(chunk) for chunk in document.chunks.order_by("chunk_index")],
    }


def create_document_from_upload(
    *,
    uploaded_file,
    title,
    source_date,
    uploaded_by=None,
    owner=None,
    owner_id=None,
    visibility=None,
    dataset=None,
    dataset_id=None,
    skip_initial_version=False,
):
    filename = uploaded_file.name
    doc_type = _detect_doc_type(filename)
    if doc_type not in {"txt", "pdf", "docx"}:
        raise ValueError("当前仅支持 txt/pdf/docx 文件上传。")

    resolved_owner = owner or uploaded_by
    parsed_owner_id = _parse_owner_id(owner_id)
    if parsed_owner_id is not None:
        User = get_user_model()
        try:
            resolved_owner = User.objects.get(id=parsed_owner_id)
        except User.DoesNotExist as exc:
            raise ValueError("owner_id 对应用户不存在。") from exc

    resolved_dataset = dataset
    parsed_dataset_id = _parse_dataset_id(dataset_id)
    if parsed_dataset_id is not None:
        try:
            resolved_dataset = Dataset.objects.get(id=parsed_dataset_id)
        except Dataset.DoesNotExist as exc:
            raise ValueError("dataset_id 对应数据集不存在。") from exc

    document = Document.objects.create(
        title=title or Path(filename).stem,
        file=uploaded_file,
        filename=filename,
        doc_type=doc_type,
        uploaded_by=uploaded_by,
        owner=resolved_owner,
        dataset=resolved_dataset,
        visibility=_parse_visibility(visibility),
        source_date=_parse_source_date(source_date),
    )
    if not skip_initial_version:
        DocumentVersion.objects.create(
            root_document=document,
            document=document,
            version_number=1,
            is_current=True,
            source_type="upload",
            source_label=document.title or document.filename,
            source_metadata={},
            processing_notes="",
        )
    return document


def list_documents(user):
    queryset = get_visible_documents_queryset(user).filter(
        Q(version_record__is_current=True) | Q(version_record__isnull=True)
    )
    return [serialize_document(document) for document in queryset]


def _parse_document_ids(raw_ids):
    if not isinstance(raw_ids, (list, tuple)):
        raise ValueError("document_ids 必须是整数数组。")

    document_ids = []
    for raw_value in raw_ids:
        if isinstance(raw_value, bool) or not isinstance(raw_value, int):
            raise ValueError("document_ids 必须是整数数组。")
        document_ids.append(raw_value)
    return document_ids


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
    version_record = _get_version_record(document)
    return {
        "document_id": document.id,
        "document_title": document.title,
        "doc_type": document.doc_type,
        "source_date": document.source_date.isoformat() if document.source_date else None,
        "dataset_id": document.dataset_id,
        "dataset_name": document.dataset.name if getattr(document, "dataset", None) else None,
        "root_document_id": _get_root_document_id(document, version_record),
        "version_number": _get_current_version_number(document, version_record),
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

    broker_url = str(getattr(settings, "CELERY_BROKER_URL", "") or "")
    should_run_inline = settings.CELERY_TASK_ALWAYS_EAGER or broker_url.startswith("memory://")

    with transaction.atomic():
        locked_document = Document.objects.select_for_update().get(id=document.id)
        latest_task = locked_document.ingestion_tasks.order_by("id").last()
        if latest_task and latest_task.status in {
            IngestionTask.STATUS_QUEUED,
            IngestionTask.STATUS_RUNNING,
        }:
            return latest_task, False

        previous_status = locked_document.status
        previous_error_message = locked_document.error_message
        next_retry_count = 0
        if latest_task and latest_task.status == IngestionTask.STATUS_FAILED:
            next_retry_count = latest_task.retry_count + 1
        elif previous_status == Document.STATUS_FAILED:
            next_retry_count = 1
        locked_document.status = Document.STATUS_UPLOADED
        locked_document.error_message = ""
        locked_document.save(update_fields=["status", "error_message", "updated_at"])
        ingestion_task = IngestionTask.objects.create(
            document=locked_document,
            status=IngestionTask.STATUS_QUEUED,
            current_step=IngestionTask.STEP_QUEUED,
            retry_count=next_retry_count,
        )

    try:
        if should_run_inline:
            async_result = ingest_document_task.apply(args=(locked_document.id, ingestion_task.id))
        else:
            async_result = ingest_document_task.delay(locked_document.id, ingestion_task.id)
    except Exception:
        _cleanup_failed_ingestion_dispatch(
            document_id=locked_document.id,
            ingestion_task_id=ingestion_task.id,
            previous_status=previous_status,
            previous_error_message=previous_error_message,
        )
        raise

    ingestion_task.celery_task_id = async_result.id or ""
    ingestion_task.save(update_fields=["celery_task_id", "updated_at"])
    return ingestion_task, True


def _cleanup_failed_ingestion_dispatch(
    *,
    document_id,
    ingestion_task_id,
    previous_status,
    previous_error_message,
):
    with transaction.atomic():
        task = (
            IngestionTask.objects.select_for_update()
            .filter(id=ingestion_task_id)
            .select_related("document")
            .first()
        )
        if task is None:
            return
        if task.status != IngestionTask.STATUS_QUEUED:
            return

        document = Document.objects.select_for_update().filter(id=document_id).first()
        task.delete()

        if document is None:
            return

        document.status = previous_status
        document.error_message = previous_error_message
        document.save(update_fields=["status", "error_message", "updated_at"])


def batch_enqueue_document_ingestion(user, document_ids):
    parsed_document_ids = _parse_document_ids(document_ids)
    accepted_count = 0
    skipped_count = 0
    failed_count = 0
    results = []

    for document_id in parsed_document_ids:
        try:
            document = get_document_for_user(user, document_id)
        except Document.DoesNotExist:
            skipped_count += 1
            results.append(
                {
                    "document_id": document_id,
                    "status": "missing",
                    "reason": "文档不存在。",
                }
            )
            continue

        try:
            ingestion_task, created = enqueue_document_ingestion(document)
        except Document.DoesNotExist:
            skipped_count += 1
            results.append(
                {
                    "document_id": document_id,
                    "status": "missing",
                    "reason": "文档不存在。",
                }
            )
            continue
        except (OperationalError, ProgrammingError, DatabaseError):
            raise
        except Exception as exc:
            failed_count += 1
            results.append(
                {
                    "document_id": document_id,
                    "status": "failed",
                    "reason": str(exc) or "入库任务提交失败。",
                }
            )
            continue

        if created:
            accepted_count += 1
            results.append(
                {
                    "document_id": document_id,
                    "status": "accepted",
                    "task_id": ingestion_task.id,
                }
            )
            continue

        skipped_count += 1
        results.append(
            {
                "document_id": document_id,
                "status": "skipped",
                "reason": "已有进行中的摄取任务。",
                "task_id": ingestion_task.id,
            }
        )

    return {
        "accepted_count": accepted_count,
        "skipped_count": skipped_count,
        "failed_count": failed_count,
        "results": results,
    }


def delete_document_with_vectors(document):
    file_field = document.file
    storage = file_field.storage
    file_name = file_field.name
    document_id = document.id
    document.delete()
    transaction.on_commit(
        lambda: _cleanup_deleted_document_artifacts(
            document_id=document_id,
            storage=storage,
            file_name=file_name,
        )
    )


def _cleanup_deleted_document_artifacts(*, document_id, storage, file_name):
    from rag.services.vector_store_service import _VECTOR_STORE

    try:
        VectorService().delete_document(document_id)
    except Exception:
        logger.exception(
            "Failed to delete knowledgebase vectors after document cleanup",
            extra={"document_id": document_id},
        )

    _VECTOR_STORE.pop(document_id, None)

    if not file_name:
        return

    try:
        file_exists = storage.exists(file_name)
    except Exception:
        logger.exception(
            "Failed to inspect knowledgebase file after document cleanup",
            extra={"document_id": document_id, "file_name": file_name},
        )
        return

    if file_exists:
        try:
            storage.delete(file_name)
        except Exception:
            logger.exception(
                "Failed to delete knowledgebase file after document cleanup",
                extra={"document_id": document_id, "file_name": file_name},
            )


def batch_delete_documents(user, document_ids):
    parsed_document_ids = _parse_document_ids(document_ids)
    deleted_count = 0
    failed_count = 0
    results = []

    for document_id in parsed_document_ids:
        try:
            with transaction.atomic():
                document = (
                    Document.objects.select_for_update()
                    .filter(_document_access_q(user))
                    .get(id=document_id)
                )

                active_ingestion_task = document.ingestion_tasks.filter(
                    status__in=[
                        IngestionTask.STATUS_QUEUED,
                        IngestionTask.STATUS_RUNNING,
                    ]
                ).order_by("id").last()
                if active_ingestion_task is not None:
                    failed_count += 1
                    results.append(
                        {
                            "document_id": document_id,
                            "status": "busy",
                            "message": "文档存在进行中的摄取任务，无法删除。",
                        }
                    )
                    continue

                delete_document_with_vectors(document)
        except Document.DoesNotExist:
            failed_count += 1
            results.append(
                {
                    "document_id": document_id,
                    "status": "missing",
                    "message": "文档不存在。",
                }
            )
            continue
        except (OperationalError, ProgrammingError, DatabaseError):
            raise
        except Exception as exc:
            failed_count += 1
            results.append(
                {
                    "document_id": document_id,
                    "status": "failed",
                    "message": str(exc) or "删除失败。",
                }
            )
            continue

        deleted_count += 1
        results.append({"document_id": document_id, "status": "deleted"})

    return {
        "deleted_count": deleted_count,
        "failed_count": failed_count,
        "results": results,
    }


def start_ingestion_task(ingestion_task):
    if ingestion_task.status == IngestionTask.STATUS_FAILED:
        ingestion_task.retry_count += 1
    _mark_ingestion_task_running(ingestion_task)
    if ingestion_task.retry_count:
        ingestion_task.save(update_fields=["retry_count", "updated_at"])
    return ingestion_task
