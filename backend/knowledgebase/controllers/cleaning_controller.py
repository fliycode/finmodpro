"""
文档清洗控制器。

类比 SpringBoot: 相当于 @RestController 中处理文档清洗操作的端点。
支持两种请求方法：
- GET:  查询文档的历史清洗结果记录
- POST: 对文档执行一次新的清洗操作
"""
import json
import logging
import time

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from common.logging import build_log_extra
from knowledgebase.controllers.audit_utils import (
    build_document_cleaning_audit_payload,
    safe_record_audit_event,
)
from knowledgebase.models import Document, DocumentCleaningResult
from knowledgebase.services.cleaning_engine_service import clean_document
from knowledgebase.services.cleaning_quality_service import serialize_cleaning_result
from rbac.services.authz_service import permission_required
from systemcheck.models import AuditRecord

logger = logging.getLogger(__name__)


@csrf_exempt
@require_http_methods(["GET", "POST"])
@permission_required("auth.view_document")
def document_cleaning_view(request, document_id):
    """
    文档清洗端点 —— GET/POST documents/{document_id}/cleaning。

    类比 SpringBoot: 相当于
        @RequestMapping(value="/documents/{documentId}/cleaning", method={GET, POST})
        @PreAuthorize("hasAuthority('auth.view_document')")
        public ResponseEntity<?> handleCleaning(@PathVariable Long documentId)

    GET:  返回该文档的所有历史清洗结果（DocumentCleaningResult 列表）。
    POST: 对该文档执行一次清洗流程（需额外拥有 auth.trigger_cleaning 权限），
          执行完成后返回清洗结果。

    参数:
        request:     Django HttpRequest 对象
        document_id: URL 路径中的文档 ID

    返回:
        GET  -> 200: {"results": [...], "total": N}
        POST -> 201: {"result": {...}}  (清洗成功)
        POST -> 500: {"message": "清洗失败: ..."}  (清洗异常)
        文档不存在 -> 404
    """
    try:
        document = Document.objects.get(id=document_id)
    except Document.DoesNotExist:
        if request.method == "POST":
            safe_record_audit_event(
                actor=request.user,
                action="knowledgebase.document.clean",
                target_type="document",
                target_id=document_id,
                status=AuditRecord.STATUS_FAILED,
                detail_payload={"error": "文档不存在。"},
            )
        return JsonResponse({"message": "文档不存在。"}, status=404)

    if request.method == "GET":
        results = DocumentCleaningResult.objects.filter(document=document)
        return JsonResponse({
            "results": [serialize_cleaning_result(r) for r in results],
            "total": results.count(),
        })

    if not request.user.has_perm("auth.trigger_cleaning"):
        return JsonResponse({"message": "无权限。"}, status=403)

    started_at = time.monotonic()
    try:
        result = clean_document(document=document)
    except Exception as exc:
        duration_ms = round((time.monotonic() - started_at) * 1000, 1)
        logger.exception(
            "Manual document cleaning failed",
            extra=build_log_extra(
                document_id=document.id,
                dataset_id=document.dataset_id,
                step="cleaning",
                status="failed",
                duration_ms=duration_ms,
                error_code="cleaning_failed",
            ),
        )
        safe_record_audit_event(
            actor=request.user,
            action="knowledgebase.document.clean",
            target_type="document",
            target_id=document.id,
            status=AuditRecord.STATUS_FAILED,
            detail_payload={"title": document.title, "error": f"清洗失败: {exc}"},
        )
        return JsonResponse({"message": f"清洗失败: {exc}"}, status=500)

    duration_ms = round((time.monotonic() - started_at) * 1000, 1)
    serialized_result = serialize_cleaning_result(result)
    logger.info(
        "Manual document cleaning completed",
        extra=build_log_extra(
            document_id=document.id,
            dataset_id=document.dataset_id,
            step="cleaning",
            status="succeeded",
            duration_ms=duration_ms,
            quality_score=result.quality_score,
            quality_gate_status=serialized_result["quality_gate"]["status"],
        ),
    )
    safe_record_audit_event(
        actor=request.user,
        action="knowledgebase.document.clean",
        target_type="document",
        target_id=document.id,
        status=AuditRecord.STATUS_SUCCEEDED,
        detail_payload=build_document_cleaning_audit_payload(
            document=document,
            result=result,
        ),
    )
    return JsonResponse({"result": serialized_result}, status=201)
