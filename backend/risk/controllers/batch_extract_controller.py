"""
批量风险抽取控制器 —— 处理多文档的批量风险提取请求。
类比 SpringBoot: 相当于 @RestController 中的 @PostMapping 方法，
提交批量抽取任务到 Celery 异步队列，支持在线（inline）执行和异步执行两种模式。
"""

from django.conf import settings

from celery.result import AsyncResult
from rest_framework.views import APIView

from common.api_response import error_response, success_response
from rbac.services.authz_service import get_authenticated_user, user_has_permission
from systemcheck.services.audit_service import record_audit_event
from risk.serializers import RiskBatchExtractionRequestSerializer


class RiskDocumentBatchExtractView(APIView):
    """
    批量文档风险抽取视图 —— POST /api/risk/documents/extract-batch

    接收一组文档 ID，为每个文档创建风险提取任务。

    类比 SpringBoot: 相当于 @PostMapping("/document/extract-batch")。
    """
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        """
        发起批量文档风险抽取。

        参数:
            request: Django HttpRequest，body 包含:
                     - document_ids (list[int], 必填): 文档 ID 列表。

        返回:
            JsonResponse: 包含 task_id 和状态信息。
                         如果是 inline 模式（执行器运行在内存中），直接返回结果。
                         如果是异步模式，返回 202 + task_id。
        """
        user = get_authenticated_user(request)
        if user is None:
            return error_response(code=401, message="未认证。", status_code=401)
        if not user_has_permission(user, "auth.trigger_ingest"):
            return error_response(code=403, message="无权限。", status_code=403)

        serializer = RiskBatchExtractionRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        document_ids = serializer.validated_data["document_ids"]

        from risk.tasks import batch_extract_document_task

        broker_url = str(getattr(settings, "CELERY_BROKER_URL", "") or "")
        should_run_inline = settings.CELERY_TASK_ALWAYS_EAGER or broker_url.startswith("memory://")

        if should_run_inline:
            try:
                batch_summary = batch_extract_document_task.apply(args=(document_ids,)).get()
            except Exception as exc:
                return error_response(code=500, message=f"批量风险抽取失败: {exc}")

            failed_documents = [
                item for item in batch_summary.get("results", [])
                if item.get("status") in {"failed", "not_found", "no_chunks"}
            ]
            record_audit_event(
                actor=user,
                action="risk.batch_extract",
                target_type="documents",
                target_id=",".join(str(did) for did in document_ids),
                status="failed" if failed_documents else "succeeded",
                detail_payload={
                    "total_documents": batch_summary.get("total_documents", 0),
                    "total_created_count": batch_summary.get("total_created_count", 0),
                    "failed_documents": len(failed_documents),
                },
            )
            return success_response(message="批量风险抽取完成。", data=batch_summary)

        result = batch_extract_document_task.delay(document_ids)
        record_audit_event(
            actor=user,
            action="risk.batch_extract",
            target_type="documents",
            target_id=",".join(str(did) for did in document_ids),
            status="submitted",
            detail_payload={"task_id": result.id, "total_documents": len(document_ids)},
        )
        return success_response(
            message="批量风险抽取任务已提交。",
            data={"task_id": result.id, "status": "PENDING"},
        )


class RiskDocumentBatchExtractRetryView(APIView):
    """
    批量文档风险抽取重试视图 —— POST /api/risk/documents/extract-batch/retry

    类比 SpringBoot: 相当于 @PostMapping("/extract-batch/retry")。
    """
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        """
        重新发起批量文档风险抽取。

        参数:
            request: Django HttpRequest，body 包含 document_ids 列表。

        返回:
            JsonResponse: 包含 task_id 和状态信息的成功响应。
        """
        user = get_authenticated_user(request)
        if user is None:
            return error_response(code=401, message="未认证。", status_code=401)
        if not user_has_permission(user, "auth.trigger_ingest"):
            return error_response(code=403, message="无权限。", status_code=403)

        serializer = RiskBatchExtractionRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        document_ids = serializer.validated_data["document_ids"]

        record_audit_event(
            actor=user,
            action="risk.batch_extract.retry",
            target_type="documents",
            target_id=",".join(str(did) for did in document_ids),
            status="retried",
            detail_payload={"retry_from_action": "risk.batch_extract", "total_documents": len(document_ids)},
        )

        from risk.tasks import batch_extract_document_task

        broker_url = str(getattr(settings, "CELERY_BROKER_URL", "") or "")
        should_run_inline = settings.CELERY_TASK_ALWAYS_EAGER or broker_url.startswith("memory://")

        if should_run_inline:
            try:
                batch_summary = batch_extract_document_task.apply(args=(document_ids,)).get()
            except Exception as exc:
                return error_response(code=500, message=f"批量风险抽取失败: {exc}")
            return success_response(message="批量风险抽取完成。", data=batch_summary)

        result = batch_extract_document_task.delay(document_ids)
        return success_response(
            message="批量风险抽取任务已提交。",
            data={"task_id": result.id, "status": "PENDING"},
        )
