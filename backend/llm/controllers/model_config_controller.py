from rest_framework.views import APIView

from common.api_response import error_response, success_response
from common.exceptions import ServiceConfigurationError, UpstreamServiceError
from llm.serializers import (
    ModelConfigActivationSerializer,
    ModelConfigConnectionTestSerializer,
    ModelConfigSummarySerializer,
    ModelConfigWriteSerializer,
)
from llm.services.model_config_command_service import (
    create_model_config,
    migrate_active_configs_to_litellm,
    set_model_config_active_state,
    test_model_config_connection,
    update_model_config,
)
from llm.services.model_config_query_service import get_model_config, list_model_configs
from rbac.services.authz_service import get_authenticated_user, user_has_permission


def _require_manage_permission(request):
    user = get_authenticated_user(request)
    if user is None:
        return None, error_response(code=401, message="未认证。", status_code=401)
    if not user_has_permission(user, "auth.manage_model_config"):
        return None, error_response(code=403, message="无权限。", status_code=403)
    return user, None


class ModelConfigListView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        _, permission_error = _require_manage_permission(request)
        if permission_error is not None:
            return permission_error

        model_configs = list_model_configs()
        return success_response(
            data={
                "total": model_configs.count(),
                "model_configs": ModelConfigSummarySerializer(model_configs, many=True).data,
            }
        )

    def post(self, request):
        _, permission_error = _require_manage_permission(request)
        if permission_error is not None:
            return permission_error

        serializer = ModelConfigWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        model_config = create_model_config(payload=serializer.validated_data)
        return success_response(data={"model_config": ModelConfigSummarySerializer(model_config).data})


class ModelConfigDetailView(APIView):
    authentication_classes = []
    permission_classes = []

    def patch(self, request, model_config_id):
        _, permission_error = _require_manage_permission(request)
        if permission_error is not None:
            return permission_error

        model_config = get_model_config(model_config_id=model_config_id)
        if model_config is None:
            return error_response(code=404, message="模型配置不存在。", status_code=404)

        serializer = ModelConfigWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        updated = update_model_config(model_config=model_config, payload=serializer.validated_data)
        return success_response(data={"model_config": ModelConfigSummarySerializer(updated).data})


class ModelConfigActivationView(APIView):
    authentication_classes = []
    permission_classes = []

    def patch(self, request, model_config_id):
        _, permission_error = _require_manage_permission(request)
        if permission_error is not None:
            return permission_error

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


class ModelConfigConnectionTestView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        _, permission_error = _require_manage_permission(request)
        if permission_error is not None:
            return permission_error

        serializer = ModelConfigConnectionTestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = {
            "capability": request.data.get("capability") or "chat",
            **serializer.validated_data,
        }
        try:
            result = test_model_config_connection(payload=payload)
        except ServiceConfigurationError as exc:
            return error_response(code=503, message=exc.message, status_code=503, data={"error": exc.code})
        except UpstreamServiceError as exc:
            return error_response(code=exc.status_code, message=exc.message, status_code=exc.status_code, data={"error": exc.code})
        return success_response(data=result)


class ModelConfigMigrateToLiteLLMView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        user, permission_error = _require_manage_permission(request)
        if permission_error is not None:
            return permission_error
        result = migrate_active_configs_to_litellm(triggered_by=user)
        return success_response(data=result)


class ModelConfigSyncLiteLLMView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request, model_config_id):
        user, permission_error = _require_manage_permission(request)
        if permission_error is not None:
            return permission_error
        model_config = get_model_config(model_config_id=model_config_id)
        if model_config is None:
            return error_response(code=404, message="模型配置不存在。", status_code=404)
        from llm.services.litellm_alias_service import sync_litellm_routes
        result = sync_litellm_routes(triggered_by=user)
        return success_response(data=result)
