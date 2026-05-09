import json
import logging
import mimetypes
from pathlib import Path

from django.conf import settings
from django.utils import timezone

from common.exceptions import ServiceConfigurationError, UpstreamServiceError
from common.observability import trace_span
from knowledgebase.models import DocumentVersion, IngestionTask
from llm.services.lightrag_proxy_service import send_lightrag_request

logger = logging.getLogger(__name__)


def get_graph_backend():
    return str(getattr(settings, "GRAPH_BACKEND", "lightrag") or "").strip().lower()


def is_graph_sync_enabled():
    backend = get_graph_backend()
    return backend == "lightrag" and bool(getattr(settings, "LIGHTRAG_SYNC_ENABLED", False))


def _serialize_source_metadata(document):
    try:
        version_record = document.version_record
    except DocumentVersion.DoesNotExist:
        version_record = None
    return version_record.source_metadata if version_record is not None else {}


def _resolve_root_document_id(document):
    try:
        version_record = document.version_record
    except DocumentVersion.DoesNotExist:
        return document.id
    return version_record.root_document_id if version_record is not None else document.id


def _build_sync_metadata(document):
    return {
        "document_id": document.id,
        "dataset_id": document.dataset_id,
        "root_document_id": _resolve_root_document_id(document),
        "doc_type": document.doc_type,
        "source_date": document.source_date.isoformat() if document.source_date else None,
        "source_metadata": _serialize_source_metadata(document),
    }


def _guess_content_type(document):
    guessed, _ = mimetypes.guess_type(document.filename or document.file.name)
    return guessed or "application/octet-stream"


def _update_graph_sync_state(
    ingestion_task,
    *,
    status,
    error_message=None,
    started_at=None,
    finished_at=None,
    graph_document_id=None,
    graph_track_id=None,
):
    ingestion_task.graph_sync_status = status
    update_fields = ["graph_sync_status", "updated_at"]

    if error_message is not None:
        ingestion_task.graph_sync_error_message = error_message
        update_fields.append("graph_sync_error_message")
    if started_at is not None:
        ingestion_task.graph_sync_started_at = started_at
        update_fields.append("graph_sync_started_at")
    if finished_at is not None:
        ingestion_task.graph_sync_finished_at = finished_at
        update_fields.append("graph_sync_finished_at")
    if graph_document_id is not None:
        ingestion_task.graph_document_id = graph_document_id
        update_fields.append("graph_document_id")
    if graph_track_id is not None:
        ingestion_task.graph_track_id = graph_track_id
        update_fields.append("graph_track_id")

    ingestion_task.save(update_fields=update_fields)


def _extract_identifier(payload, *keys):
    if not isinstance(payload, dict):
        return ""
    for key in keys:
        value = payload.get(key)
        if value in (None, ""):
            continue
        return str(value)
    return ""


def sync_document_to_graph(*, document, ingestion_task=None):
    backend = get_graph_backend()

    if backend != "lightrag" or not getattr(settings, "LIGHTRAG_SYNC_ENABLED", False):
        if ingestion_task is not None:
            _update_graph_sync_state(
                ingestion_task,
                status=IngestionTask.GRAPH_SYNC_STATUS_SKIPPED,
                error_message="",
                started_at=None,
                finished_at=timezone.now(),
                graph_document_id="",
                graph_track_id="",
            )
        return {"status": IngestionTask.GRAPH_SYNC_STATUS_SKIPPED, "payload": {}}

    if not str(getattr(settings, "LIGHTRAG_INTERNAL_URL", "") or "").strip():
        raise ServiceConfigurationError(
            "LightRAG 内部服务地址未配置，无法执行图谱同步。",
            code="lightrag_not_configured",
            provider="lightrag",
        )

    started_at = timezone.now()
    if ingestion_task is not None:
        _update_graph_sync_state(
            ingestion_task,
            status=IngestionTask.GRAPH_SYNC_STATUS_RUNNING,
            error_message="",
            started_at=started_at,
            finished_at=None,
            graph_document_id="",
            graph_track_id="",
        )

    upload_name = document.filename or Path(document.file.name).name
    form_data = {
        "title": document.title,
        "doc_id": str(document.id),
        "metadata": json.dumps(_build_sync_metadata(document), ensure_ascii=False),
    }

    try:
        document.file.open("rb")
        upload_file = document.file.file
        payload = send_lightrag_request(
            method="POST",
            upstream_path="documents/upload",
            form_data=form_data,
            files=[
                (
                    "file",
                    (
                        upload_name,
                        upload_file,
                        _guess_content_type(document),
                    ),
                )
            ],
            enforce_allow_list=True,
        )
    except (ServiceConfigurationError, UpstreamServiceError, OSError, ValueError) as exc:
        if ingestion_task is not None:
            _update_graph_sync_state(
                ingestion_task,
                status=IngestionTask.GRAPH_SYNC_STATUS_FAILED,
                error_message=str(exc) or "图谱同步失败。",
                finished_at=timezone.now(),
                graph_document_id="",
                graph_track_id="",
            )
        raise
    finally:
        try:
            document.file.close()
        except Exception:
            logger.debug("failed to close document file after graph sync", exc_info=True)

    graph_document_id = _extract_identifier(payload, "doc_id", "document_id", "id")
    graph_track_id = _extract_identifier(payload, "track_id", "task_id", "job_id")

    if ingestion_task is not None:
        _update_graph_sync_state(
            ingestion_task,
            status=IngestionTask.GRAPH_SYNC_STATUS_SUCCEEDED,
            error_message="",
            finished_at=timezone.now(),
            graph_document_id=graph_document_id,
            graph_track_id=graph_track_id,
        )

    return {
        "status": IngestionTask.GRAPH_SYNC_STATUS_SUCCEEDED,
        "payload": payload,
        "graph_document_id": graph_document_id,
        "graph_track_id": graph_track_id,
    }


def sync_document_to_graph_with_trace(*, document, ingestion_task=None):
    with trace_span(
        "knowledgebase.graph_sync",
        metadata={"document_id": document.id},
        input_data={"document_title": document.title},
    ) as observation:
        result = sync_document_to_graph(document=document, ingestion_task=ingestion_task)
        observation.update(output={"status": result["status"]})
        return result
