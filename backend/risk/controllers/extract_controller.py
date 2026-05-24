"""
单文档风险抽取控制器 —— 处理单文档风险提取、重试和状态查询。
类比 SpringBoot: 相当于 @RestController 中的 @PostMapping / @GetMapping 方法，
管理风险提取任务的完整生命周期。
"""

from django.conf import settings
from django.core.exceptions import ValidationError

from celery.result import AsyncResult
from rest_framework.views import APIView

from common.api_response import error_response, success_response
from knowledgebase.models import Document
from rbac.services.authz_service import get_authenticated_user, user_has_permission
from risk.models import RiskExtractionTask
from risk.services.task_service import (
    RiskExtractionBusyError,
    expire_stale_risk_extractions,
    get_risk_extraction_failure_status_code,
    serialize_risk_extraction_task,
    submit_risk_extraction,
)
from systemcheck.services.audit_service import record_audit_event


class RiskDocumentExtractView(APIView):
    """
    单文档风险抽取视图 —— POST /api/risk/documents/{document_id}/extract

    为指定文档创建风险提取任务。

    类比 SpringBoot: 相当于 @PostMapping("/documents/{documentId}/extract")。
    """
    authentication_classes = []
    permission_classes = []

    def post(self, request, document_id):
        """
        发起单文档风险抽取。

        参数:
            request: Django HttpRequest。
            document_id (int): 路径参数，文档 ID。

        返回:
            JsonResponse:
            - 201: inline 模式且成功（有提取结果）
            - 200: inline 模式且无提取结果（no_chunks / no_signals）
            - 202: 异步任务已提交
            - 429: 队列繁忙
            - 404/500: 错误
        """
        user = get_authenticated_user(request)
        if user is None:
            return error_response(code=401, message="未认证。", status_code=401)
        if not user_has_permission(user, "auth.trigger_ingest"):
            return error_response(code=403, message="无权限。", status_code=403)

        try:
            document = Document.objects.get(id=document_id)
        except Document.DoesNotExist:
            return error_response(code=404, message="文档不存在。", status_code=404)

        should_run_inline = settings.CELERY_TASK_ALWAYS_EAGER

        try:
            task, created = submit_risk_extraction(document)
        except RiskExtractionBusyError as exc:
            busy_payload = {
                "task_id": None,
                "document_id": document.id,
                "status": "BUSY",
                "progress": 100,
                "message": exc.message,
                "error_code": RiskExtractionTask.ERROR_BUSY,
            }
            record_audit_event(
                actor=user,
                action="risk.extract",
                target_type="document",
                target_id=document.id,
                status="blocked",
                detail_payload={"error_code": RiskExtractionTask.ERROR_BUSY},
            )
            return error_response(
                code=429,
                message=exc.message,
                data=busy_payload,
                status_code=429,
            )
        if should_run_inline:
            task.refresh_from_db()
        task_payload = serialize_risk_extraction_task(task)

        if should_run_inline and task.status == RiskExtractionTask.STATUS_SUCCEEDED:
            result_status = task.result_payload.get("status")
            record_audit_event(
                actor=user,
                action="risk.extract",
                target_type="document",
                target_id=document.id,
                status="succeeded",
                detail_payload={"created_count": task.created_count, "task_id": str(task.id)},
            )
            return success_response(
                message=task.message or "风险抽取完成。",
                data=task.result_payload,
                status_code=200 if result_status in {"no_chunks", "no_signals"} else 201,
            )

        if should_run_inline and task.status == RiskExtractionTask.STATUS_FAILED:
            record_audit_event(
                actor=user,
                action="risk.extract",
                target_type="document",
                target_id=document.id,
                status="failed",
                detail_payload={"message": task.error_message, "task_id": str(task.id)},
            )
            return error_response(
                code=get_risk_extraction_failure_status_code(task),
                message=task.error_message or "风险抽取失败。",
                data=task_payload,
                status_code=get_risk_extraction_failure_status_code(task),
            )

        record_audit_event(
            actor=user,
            action="risk.extract",
            target_type="document",
            target_id=document.id,
            status="submitted" if created else "skipped",
            detail_payload={"task_id": str(task.id)},
        )
        return success_response(
            message="风险抽取任务已提交。" if created else "已有进行中的风险抽取任务。",
            data=task_payload,
            status_code=202,
        )


class RiskDocumentExtractRetryView(APIView):
    """
    单文档风险抽取重试视图 —— POST /api/risk/documents/{document_id}/extract/retry

    类比 SpringBoot: 相当于 @PostMapping("/{documentId}/extract/retry")。
    """
    authentication_classes = []
    permission_classes = []

    def post(self, request, document_id):
        """
        重新发起单文档风险抽取。

        参数:
            request: Django HttpRequest。
            document_id (int): 路径参数，文档 ID。

        返回:
            JsonResponse: 任务状态和数据。
        """
        user = get_authenticated_user(request)
        if user is None:
            return error_response(code=401, message="未认证。", status_code=401)
        if not user_has_permission(user, "auth.trigger_ingest"):
            return error_response(code=403, message="无权限。", status_code=403)

        try:
            document = Document.objects.get(id=document_id)
        except Document.DoesNotExist:
            return error_response(code=404, message="文档不存在。", status_code=404)

        record_audit_event(
            actor=user,
            action="risk.extract.retry",
            target_type="document",
            target_id=document.id,
            status="retried",
            detail_payload={"retry_from_action": "risk.extract"},
        )

        should_run_inline = settings.CELERY_TASK_ALWAYS_EAGER

        try:
            task, _created = submit_risk_extraction(document)
        except RiskExtractionBusyError as exc:
            return error_response(
                code=429,
                message=exc.message,
                data={
                    "task_id": None,
                    "document_id": document.id,
                    "status": "BUSY",
                    "progress": 100,
                    "message": exc.message,
                    "error_code": RiskExtractionTask.ERROR_BUSY,
                },
                status_code=429,
            )
        if should_run_inline:
            task.refresh_from_db()
        task_payload = serialize_risk_extraction_task(task)

        if should_run_inline and task.status == RiskExtractionTask.STATUS_SUCCEEDED:
            result_status = task.result_payload.get("status")
            return success_response(
                message=task.message or "风险抽取完成。",
                data=task.result_payload,
                status_code=200 if result_status in {"no_chunks", "no_signals"} else 201,
            )

        if should_run_inline and task.status == RiskExtractionTask.STATUS_FAILED:
            return error_response(
                code=get_risk_extraction_failure_status_code(task),
                message=task.error_message or "风险抽取失败。",
                data=task_payload,
                status_code=get_risk_extraction_failure_status_code(task),
            )

        return success_response(
            message="风险抽取任务已提交。",
            data=task_payload,
            status_code=202,
        )


class RiskExtractStatusView(APIView):
    """
    风险抽取任务状态查询视图 —— GET /api/risk/documents/extract/status/{task_id}

    类比 SpringBoot: 相当于 @GetMapping("/extract/status/{taskId}")。
    """
    authentication_classes = []
    permission_classes = []

    def get(self, request, task_id):
        """
        查询风险抽取任务的状态和进度。

        参数:
            request: Django HttpRequest。
            task_id (str): 路径参数，任务 UUID。

        返回:
            JsonResponse: 任务状态、进度、消息和结果数据。
        """
        user = get_authenticated_user(request)
        if user is None:
            return error_response(code=401, message="未认证。", status_code=401)

        expire_stale_risk_extractions()

        try:
            task = RiskExtractionTask.objects.filter(id=task_id).select_related("document").first()
        except (ValidationError, ValueError):
            task = None
        if task is not None:
            payload = serialize_risk_extraction_task(task)
            if task.status == RiskExtractionTask.STATUS_FAILED:
                return error_response(
                    code=get_risk_extraction_failure_status_code(task),
                    message=task.error_message or "风险抽取任务失败。",
                    data=payload,
                    status_code=get_risk_extraction_failure_status_code(task),
                )
            return success_response(data=payload)

        result = AsyncResult(task_id)
        if result.state == "PENDING":
            return success_response(data={"task_id": task_id, "status": "PENDING", "progress": 0})
        if result.state == "FAILURE":
            return error_response(
                code=500,
                message=f"风险抽取任务失败: {result.result}",
                data={"task_id": task_id, "status": "FAILURE", "progress": 100},
            )
        if result.state == "SUCCESS":
            return success_response(
                data={"task_id": task_id, "status": "SUCCESS", "progress": 100, "result": result.result}
            )
        return success_response(data={"task_id": task_id, "status": result.state, "progress": 72})
