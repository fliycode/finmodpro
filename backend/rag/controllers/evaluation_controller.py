from rest_framework.views import APIView

from common.api_response import error_response, success_response
from rag.services.retrieval_evaluation_service import (
    evaluate_generation_fixture,
    evaluate_retrieval_fixture,
)
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

        data = {}
        try:
            if mode in ("retrieval", "all"):
                data["retrieval"] = evaluate_retrieval_fixture()
            if mode in ("generation", "all"):
                data["generation"] = evaluate_generation_fixture()
        except Exception as exc:
            return error_response(code=500, message=f"评测执行失败: {exc}")

        return success_response(data=data)
