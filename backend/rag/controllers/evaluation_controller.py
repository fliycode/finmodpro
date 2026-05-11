from django.conf import settings

from celery.result import AsyncResult
from rest_framework.views import APIView

from common.api_response import error_response, success_response
from rbac.services.authz_service import get_authenticated_user, user_has_permission


class RagEvaluationView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        user = get_authenticated_user(request)
        if user is None:
            return error_response(code=401, message="未认证。", status_code=401)
        if not user_has_permission(user, "auth.run_evaluation"):
            return error_response(code=403, message="无权限。", status_code=403)

        mode = request.data.get("mode", "all")
        if mode not in ("retrieval", "generation", "all"):
            return error_response(
                code=400, message="mode 必须为 retrieval、generation 或 all。"
            )

        from rag.tasks import run_evaluation_task

        broker_url = str(getattr(settings, "CELERY_BROKER_URL", "") or "")
        should_run_inline = settings.CELERY_TASK_ALWAYS_EAGER or broker_url.startswith("memory://")

        if should_run_inline:
            try:
                data = run_evaluation_task.apply(args=(mode,)).get()
            except Exception as exc:
                return error_response(code=500, message=f"评测执行失败: {exc}")
            return success_response(data=data)

        result = run_evaluation_task.delay(mode)
        return success_response(
            message="评测任务已提交，请轮询结果。",
            data={"task_id": result.id, "status": "PENDING"},
        )


class RagEvaluationStatusView(APIView):
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
                message=f"评测任务失败: {result.result}",
                data={"task_id": task_id, "status": "FAILURE"},
            )
        if result.state == "SUCCESS":
            return success_response(
                data={"task_id": task_id, "status": "SUCCESS", "result": result.result}
            )
        return success_response(data={"task_id": task_id, "status": result.state})
