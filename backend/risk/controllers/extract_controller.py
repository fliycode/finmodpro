from django.conf import settings

from celery.result import AsyncResult
from rest_framework.views import APIView

from common.api_response import error_response, success_response
from knowledgebase.models import Document
from rbac.services.authz_service import get_authenticated_user, user_has_permission
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

        from risk.tasks import extract_document_task

        broker_url = str(getattr(settings, "CELERY_BROKER_URL", "") or "")
        should_run_inline = settings.CELERY_TASK_ALWAYS_EAGER or broker_url.startswith("memory://")

        if should_run_inline:
            try:
                result_data = extract_document_task.apply(args=(document.id,)).get()
            except Exception as exc:
                record_audit_event(
                    actor=user,
                    action="risk.extract",
                    target_type="document",
                    target_id=document.id,
                    status="failed",
                    detail_payload={"message": str(exc)},
                )
                return error_response(code=500, message=f"风险抽取失败: {exc}")

            record_audit_event(
                actor=user,
                action="risk.extract",
                target_type="document",
                target_id=document.id,
                status="succeeded" if result_data.get("status") == "succeeded" else "failed",
                detail_payload={"created_count": result_data.get("created_count", 0)},
            )
            if result_data.get("status") == "succeeded":
                return success_response(message=result_data["message"], data=result_data, status_code=201)
            return error_response(code=500, message=result_data.get("message", "风险抽取失败。"), data=result_data)

        result = extract_document_task.delay(document.id)
        record_audit_event(
            actor=user,
            action="risk.extract",
            target_type="document",
            target_id=document.id,
            status="submitted",
            detail_payload={"task_id": result.id},
        )
        return success_response(
            message="风险抽取任务已提交。",
            data={"task_id": result.id, "status": "PENDING", "document_id": document.id},
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

        from risk.tasks import extract_document_task

        broker_url = str(getattr(settings, "CELERY_BROKER_URL", "") or "")
        should_run_inline = settings.CELERY_TASK_ALWAYS_EAGER or broker_url.startswith("memory://")

        if should_run_inline:
            try:
                result_data = extract_document_task.apply(args=(document.id,)).get()
            except Exception as exc:
                return error_response(code=500, message=f"风险抽取失败: {exc}")

            if result_data.get("status") == "succeeded":
                return success_response(message=result_data["message"], data=result_data, status_code=201)
            return error_response(code=500, message=result_data.get("message", "风险抽取失败。"), data=result_data)

        result = extract_document_task.delay(document.id)
        return success_response(
            message="风险抽取任务已提交。",
            data={"task_id": result.id, "status": "PENDING", "document_id": document.id},
        )


class RiskExtractStatusView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request, task_id):
        user = get_authenticated_user(request)
        if user is None:
            return error_response(code=401, message="未认证。", status_code=401)

        result = AsyncResult(task_id)
        if result.state == "PENDING":
            return success_response(data={"task_id": task_id, "status": "PENDING"})
        if result.state == "FAILURE":
            return error_response(
                code=500,
                message=f"风险抽取任务失败: {result.result}",
                data={"task_id": task_id, "status": "FAILURE"},
            )
        if result.state == "SUCCESS":
            return success_response(
                data={"task_id": task_id, "status": "SUCCESS", "result": result.result}
            )
        return success_response(data={"task_id": task_id, "status": result.state})
