from rest_framework.views import APIView

from common.api_response import error_response, success_response
from llm.serializers import ModelConfigActivationSerializer, ModelConfigSummarySerializer
from llm.services.model_config_command_service import set_model_config_active_state
from llm.services.model_config_query_service import list_model_configs
from rbac.services.authz_service import get_authenticated_user, user_has_permission


class ModelConfigListView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        user = get_authenticated_user(request)
        if user is None:
            return error_response(code=401, message="未认证。", status_code=401)
        if not user_has_permission(user, "auth.manage_model_config"):
            return error_response(code=403, message="无权限。", status_code=403)

        model_configs = list_model_configs()
        return success_response(
            data={
                "total": model_configs.count(),
                "model_configs": ModelConfigSummarySerializer(model_configs, many=True).data,
            }
        )


class ModelConfigActivationView(APIView):
    authentication_classes = []
    permission_classes = []

    def patch(self, request, model_config_id):
        user = get_authenticated_user(request)
        if user is None:
            return error_response(code=401, message="未认证。", status_code=401)
        if not user_has_permission(user, "auth.manage_model_config"):
            return error_response(code=403, message="无权限。", status_code=403)

        serializer = ModelConfigActivationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            model_config = set_model_config_active_state(
                model_config_id=model_config_id,
                is_active=serializer.validated_data["is_active"],
            )
        except ValueError:
            return error_response(code=404, message="模型配置不存在。", status_code=404)

        return success_response(
            data={"model_config": ModelConfigSummarySerializer(model_config).data}
        )
