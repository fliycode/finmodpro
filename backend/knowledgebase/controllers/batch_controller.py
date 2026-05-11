import json

from django.db import DatabaseError, OperationalError, ProgrammingError
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from knowledgebase.controllers.audit_utils import (
    build_document_batch_audit_payload,
    build_document_batch_delete_audit_payload,
    safe_record_audit_event,
    summarize_document_ids,
)
from knowledgebase.services.document_service import (
    batch_delete_documents,
    batch_enqueue_document_ingestion,
)
from rbac.services.authz_service import permission_required
from systemcheck.models import AuditRecord


def _build_schema_not_ready_response(exc):
    return JsonResponse(
        {
            "message": "知识库数据表尚未初始化，请先执行后端迁移与 RBAC 初始化。",
            "detail": str(exc),
        },
        status=503,
    )


def _parse_request_payload(request):
    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise ValueError("请求体必须是合法 JSON。")
    if not isinstance(payload, dict):
        raise ValueError("请求体必须是 JSON 对象。")
    return payload


@csrf_exempt
@require_POST
@permission_required("auth.trigger_ingest")
def document_batch_ingest_view(request):
    try:
        payload = _parse_request_payload(request)
    except ValueError as exc:
        safe_record_audit_event(
            actor=request.user,
            action="knowledgebase.document.batch_ingest",
            target_type="document",
            status=AuditRecord.STATUS_FAILED,
            detail_payload={"error": str(exc)},
        )
        return JsonResponse({"message": str(exc)}, status=400)

    document_ids = payload.get("document_ids", [])
    try:
        result = batch_enqueue_document_ingestion(
            request.user,
            document_ids,
        )
        audit_status = (
            AuditRecord.STATUS_SUBMITTED
            if result["accepted_count"] > 0
            else AuditRecord.STATUS_FAILED
            if result["failed_count"] > 0
            else AuditRecord.STATUS_SKIPPED
        )
        safe_record_audit_event(
            actor=request.user,
            action="knowledgebase.document.batch_ingest",
            target_type="document",
            status=audit_status,
            detail_payload=build_document_batch_audit_payload(
                document_ids=document_ids,
                result=result,
            ),
        )
        return JsonResponse(result)
    except ValueError as exc:
        safe_record_audit_event(
            actor=request.user,
            action="knowledgebase.document.batch_ingest",
            target_type="document",
            status=AuditRecord.STATUS_FAILED,
            detail_payload={
                **summarize_document_ids(document_ids if isinstance(document_ids, list) else []),
                "error": str(exc),
            },
        )
        return JsonResponse({"message": str(exc)}, status=400)
    except (OperationalError, ProgrammingError, DatabaseError) as exc:
        return _build_schema_not_ready_response(exc)


@csrf_exempt
@require_POST
@permission_required("auth.delete_document")
def document_batch_delete_view(request):
    try:
        payload = _parse_request_payload(request)
    except ValueError as exc:
        safe_record_audit_event(
            actor=request.user,
            action="knowledgebase.document.batch_delete",
            target_type="document",
            status=AuditRecord.STATUS_FAILED,
            detail_payload={"error": str(exc)},
        )
        return JsonResponse({"message": str(exc)}, status=400)

    document_ids = payload.get("document_ids", [])
    try:
        result = batch_delete_documents(
            request.user,
            document_ids,
        )
        audit_status = (
            AuditRecord.STATUS_SUCCEEDED
            if result["failed_count"] == 0
            else AuditRecord.STATUS_FAILED
        )
        safe_record_audit_event(
            actor=request.user,
            action="knowledgebase.document.batch_delete",
            target_type="document",
            status=audit_status,
            detail_payload=build_document_batch_delete_audit_payload(
                document_ids=document_ids,
                result=result,
            ),
        )
        return JsonResponse(result)
    except ValueError as exc:
        safe_record_audit_event(
            actor=request.user,
            action="knowledgebase.document.batch_delete",
            target_type="document",
            status=AuditRecord.STATUS_FAILED,
            detail_payload={
                **summarize_document_ids(document_ids if isinstance(document_ids, list) else []),
                "error": str(exc),
            },
        )
        return JsonResponse({"message": str(exc)}, status=400)
    except (OperationalError, ProgrammingError, DatabaseError) as exc:
        return _build_schema_not_ready_response(exc)
