from django.conf import settings
from django.core.exceptions import ValidationError

from celery.result import AsyncResult
from rest_framework.views import APIView

from common.api_response import error_response, success_response
from knowledgebase.models import Document
from rbac.services.authz_service import get_authenticated_user, user_has_permission
from risk.models import RiskExtractionTask
from risk.services.task_service import serialize_risk_extraction_task, submit_risk_extraction
from systemcheck.services.audit_service import record_audit_event


class RiskDocumentExtractView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request, document_id):
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

        task, created = submit_risk_extraction(document)
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
                code=500,
                message=task.error_message or "风险抽取失败。",
                data=task_payload,
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
    authentication_classes = []
    permission_classes = []

    def post(self, request, document_id):
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

        task, _created = submit_risk_extraction(document)
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
                code=500,
                message=task.error_message or "风险抽取失败。",
                data=task_payload,
            )

        return success_response(
            message="风险抽取任务已提交。",
            data=task_payload,
            status_code=202,
        )


class RiskExtractStatusView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request, task_id):
        user = get_authenticated_user(request)
        if user is None:
            return error_response(code=401, message="未认证。", status_code=401)

        try:
            task = RiskExtractionTask.objects.filter(id=task_id).select_related("document").first()
        except (ValidationError, ValueError):
            task = None
        if task is not None:
            payload = serialize_risk_extraction_task(task)
            if task.status == RiskExtractionTask.STATUS_FAILED:
                return error_response(
                    code=500,
                    message=task.error_message or "风险抽取任务失败。",
                    data=payload,
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
