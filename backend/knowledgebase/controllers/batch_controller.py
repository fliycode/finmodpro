import json

from django.db import DatabaseError, OperationalError, ProgrammingError
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from knowledgebase.services.document_service import (
    batch_delete_documents,
    batch_enqueue_document_ingestion,
)
from rbac.services.authz_service import permission_required


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
    except json.JSONDecodeError:
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
        return JsonResponse({"message": str(exc)}, status=400)

    try:
        return JsonResponse(
            batch_enqueue_document_ingestion(
                request.user,
                payload.get("document_ids") or [],
            )
        )
    except ValueError as exc:
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
        return JsonResponse({"message": str(exc)}, status=400)

    try:
        return JsonResponse(
            batch_delete_documents(
                request.user,
                payload.get("document_ids") or [],
            )
        )
    except ValueError as exc:
        return JsonResponse({"message": str(exc)}, status=400)
    except (OperationalError, ProgrammingError, DatabaseError) as exc:
        return _build_schema_not_ready_response(exc)
