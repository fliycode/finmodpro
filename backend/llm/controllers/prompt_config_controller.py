from rest_framework.views import APIView

from common.api_response import error_response, success_response
from llm.serializers import PromptConfigSummarySerializer
from llm.services.prompt_query_service import list_prompt_configs
from rbac.services.authz_service import get_authenticated_user, user_has_permission


class PromptConfigListView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        user = get_authenticated_user(request)
        if user is None:
            return error_response(code=401, message="未认证。", status_code=401)
        if not user_has_permission(user, "auth.manage_model_config"):
            return error_response(code=403, message="无权限。", status_code=403)

        prompt_configs = list_prompt_configs()
        return success_response(
            data={
                "total": len(prompt_configs),
                "prompt_configs": PromptConfigSummarySerializer(prompt_configs, many=True).data,
            }
        )
