"""
文档摄取控制器 —— 触发文档进入处理管线。

类比 SpringBoot: 相当于 @RestController 中触发异步处理作业的端点。
类比 Spring 的 @Async 或 Spring Batch 的 JobLauncher：
POST 请求将文档提交到 Celery 异步任务队列，由后台 Worker 依次执行
解析 -> 清洗 -> 分块 -> 索引 -> 图谱同步 的完整管线。

支持重试机制：当文档处于 failed 状态时重新提交。
"""
from django.db import DatabaseError, OperationalError, ProgrammingError
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from common.exceptions import DocumentQualityGateError
from knowledgebase.models import Document
from knowledgebase.services.document_service import (
    build_document_response,
    enqueue_document_ingestion,
    get_document_for_user,
)
from rbac.services.authz_service import permission_required
from systemcheck.services.audit_service import record_audit_event


def _build_schema_not_ready_response(exc):
    """
    构建"数据库未就绪"的统一错误响应。

    类比 SpringBoot: 相当于 @ControllerAdvice 中针对数据库异常的全局处理逻辑。

    参数:
        exc: 捕获到的数据库异常对象

    返回:
        JsonResponse: 状态码 503。
    """
    return JsonResponse(
        {
            "message": "知识库数据表尚未初始化，请先执行后端迁移与 RBAC 初始化。",
            "detail": str(exc),
        },
        status=503,
    )


def _safe_record_audit_event(**kwargs):
    """
    安全地记录审计事件 —— 数据库异常时静默失败。

    类比 SpringBoot: 相当于带 try-catch 容错的 @EventListener，
    确保审计日志写入失败不会中断主业务流程。

    参数:
        **kwargs: 传递给 record_audit_event() 的所有参数。

    返回:
        无显式返回值，异常时 return 跳过。
    """
    try:
        record_audit_event(**kwargs)
    except (OperationalError, ProgrammingError, DatabaseError):
        return


@csrf_exempt
@require_POST
@permission_required("auth.trigger_ingest")
def document_ingest_view(request, document_id):
    """
    文档摄取端点 —— POST documents/{document_id}/ingest。

    类比 SpringBoot: 相当于
        @PostMapping("/documents/{documentId}/ingest")
        @PreAuthorize("hasAuthority('auth.trigger_ingest')")
        public ResponseEntity<?> triggerIngest(@PathVariable Long documentId)

    将文档提交到后台异步处理管线（Celery Worker）。
    如果文档已有一个进行中的摄取任务，返回提示信息（不重复创建）。
    如果文档此前失败，此次为"重试"。

    摄取管线步骤：解析 -> 清洗 -> 分块 -> 索引 -> 图谱同步

    参数:
        request:     Django HttpRequest 对象
        document_id: URL 路径中的文档 ID

    返回:
        200: {"document": {...}, "message": "已有进行中的摄取任务。"}  (任务已存在)
        200: {"document": {...}, "message": "摄取任务已提交。"}  (任务创建成功)
        404: {"message": "文档不存在。"}
        422: {"message": "..."}  (质量门禁未通过，quality_gate_blocked)
        500: {"message": "..."}  (摄取过程异常)
        503: 数据库未就绪
    """
    try:
        document = get_document_for_user(request.user, document_id)
    except Document.DoesNotExist:
        return JsonResponse({"message": "文档不存在。"}, status=404)
    except (OperationalError, ProgrammingError, DatabaseError) as exc:
        return _build_schema_not_ready_response(exc)

    try:
        previous_status = document.status
        ingestion_task, created = enqueue_document_ingestion(document)
        document.refresh_from_db()
        audit_status = "retried" if previous_status == Document.STATUS_FAILED and created else ("succeeded" if created else "skipped")
        _safe_record_audit_event(
            actor=request.user,
            action="knowledgebase.ingest",
            target_type="document",
            target_id=document.id,
            status=audit_status,
            detail_payload={
                "task_id": ingestion_task.id,
                "retry_count": getattr(ingestion_task, "retry_count", 0),
                "document_status": document.status,
            },
        )

        return JsonResponse(
            build_document_response(
                document,
                include_content_preview=True,
                message="摄取任务已提交。" if created else "已有进行中的摄取任务。",
            )
        )
    except (OperationalError, ProgrammingError, DatabaseError) as exc:
        _safe_record_audit_event(
            actor=getattr(request, "user", None),
            action="knowledgebase.ingest",
            target_type="document",
            target_id=document_id,
            status="failed",
            detail_payload={"error": str(exc)},
        )
        return _build_schema_not_ready_response(exc)
    except DocumentQualityGateError as exc:
        _safe_record_audit_event(
            actor=getattr(request, "user", None),
            action="knowledgebase.ingest",
            target_type="document",
            target_id=document_id,
            status="failed",
            detail_payload={
                "error": exc.message,
                "quality_score": exc.score,
                "quality_gate_status": exc.quality_gate["status"],
            },
        )
        return JsonResponse({"message": exc.message}, status=422)
    except Exception as exc:
        _safe_record_audit_event(
            actor=getattr(request, "user", None),
            action="knowledgebase.ingest",
            target_type="document",
            target_id=document_id,
            status="failed",
            detail_payload={"error": str(exc)},
        )
        return JsonResponse({"message": str(exc) or "文档摄取失败。"}, status=500)
