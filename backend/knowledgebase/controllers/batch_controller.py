"""
批量文档操作控制器。

类比 SpringBoot: 相当于 @RestController 中处理批量操作的端点方法。
每个视图函数对应一个 HTTP 端点，处理 JSON 请求并返回 JSON 响应。

提供两个批量操作端点：
- POST documents/batch/ingest: 批量提交文档进入摄取管线
- POST documents/batch/delete: 批量删除文档及其向量数据
"""
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
    """
    构建"数据库未就绪"的统一错误响应。

    类比 SpringBoot: 相当于全局异常处理器 (@ControllerAdvice) 中针对
    DatabaseError 的统一处理逻辑。当数据库表尚未迁移初始化时返回 503。

    参数:
        exc: 捕获到的数据库异常对象

    返回:
        JsonResponse: 状态码 503，消息体为中文提示信息。
    """
    return JsonResponse(
        {
            "message": "知识库数据表尚未初始化，请先执行后端迁移与 RBAC 初始化。",
            "detail": str(exc),
        },
        status=503,
    )


def _parse_request_payload(request):
    """
    从 HTTP 请求体中解析 JSON 负载。

    类比 SpringBoot: 相当于 @RequestBody 注解 + Jackson 反序列化的组合，
    同时包含输入校验（必须是合法 JSON 对象）。

    参数:
        request: Django HttpRequest 对象

    返回:
        dict: 解析出的 JSON 字典对象。

    抛出:
        ValueError: 当请求体不是合法 JSON 或不是 JSON 对象时抛出。
    """
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
    """
    批量文档摄取端点 —— POST documents/batch/ingest。

    类比 SpringBoot: 相当于
        @PostMapping("/documents/batch/ingest")
        @PreAuthorize("hasAuthority('auth.trigger_ingest')")
        public ResponseEntity<?> batchIngest(@RequestBody Map payload)

    从 JSON 请求体中获取 document_ids 列表，批量将其加入摄取队列。

    参数:
        request: Django HttpRequest 对象，body 中需包含 {"document_ids": [1, 2, 3]}

    返回:
        JsonResponse: 包含 accepted_count、skipped_count、failed_count 的结果字典。
                      参数校验失败返回 400，数据库未就绪返回 503。
    """
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
    """
    批量文档删除端点 —— POST documents/batch/delete。

    类比 SpringBoot: 相当于
        @PostMapping("/documents/batch/delete")
        @PreAuthorize("hasAuthority('auth.delete_document')")
        public ResponseEntity<?> batchDelete(@RequestBody Map payload)

    从 JSON 请求体中获取 document_ids 列表，批量删除文档及其关联的向量数据。

    参数:
        request: Django HttpRequest 对象，body 中需包含 {"document_ids": [1, 2, 3]}

    返回:
        JsonResponse: 包含 deleted_count、failed_count 的结果字典。
                      参数校验失败返回 400，数据库未就绪返回 503。
    """
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
