"""
模型配置控制器（类比 SpringBoot 中 @RestController）。
提供模型配置的 CRUD 操作、启用/禁用切换和连接测试。
是 LLM 管理后台最核心的控制面，所有操作均需要 auth.manage_model_config 权限。
"""
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
    delete_model_config,
    set_model_config_active_state,
    test_model_config_connection,
    update_model_config,
)
from llm.services.model_config_query_service import (
    get_model_config,
    get_model_config_overview,
    list_model_configs,
)
from rbac.services.authz_service import get_authenticated_user, user_has_permission
from systemcheck.models import AuditRecord
from systemcheck.services.audit_service import record_audit_event


def _require_manage_permission(request):
    """统一的权限守卫函数，检查用户是否具有模型配置管理权限。

    参数:
        request: Django REST Framework 的 Request 对象。
    返回:
        (user, error_response) 元组：
        - 若认证失败或权限不足，返回 (None, 错误响应对象)。
        - 若通过，返回 (user, None)。
    类比 SpringBoot 中 @PreAuthorize 注解 + SecurityContext 的组合。
    """
    user = get_authenticated_user(request)
    if user is None:
        return None, error_response(code=401, message="未认证。", status_code=401)
    if not user_has_permission(user, "auth.manage_model_config"):
        return None, error_response(code=403, message="无权限。", status_code=403)
    return user, None


def _build_model_config_audit_payload(model_config):
    """构建模型配置的审计日志负载。

    参数:
        model_config: ModelConfig 实例。
    返回:
        dict，包含模型配置关键字段的快照，用于审计记录。
    """
    return {
        "name": model_config.name,
        "capability": model_config.capability,
        "provider": model_config.provider,
        "model_name": model_config.model_name,
        "parameter_scale": model_config.parameter_scale,
        "endpoint": model_config.endpoint,
        "is_active": bool(model_config.is_active),
        "has_api_key": bool((model_config.options or {}).get("api_key")),
        "price_currency": model_config.price_currency,
    }


def _build_model_config_test_payload(payload):
    """构建连接测试的审计日志负载。

    参数:
        payload: dict，测试请求的载荷。
    返回:
        dict，包含测试相关字段的快照。
    """
    return {
        "model_config_id": payload.get("model_config_id") or "",
        "capability": payload.get("capability") or "",
        "provider": payload.get("provider") or "",
        "model_name": payload.get("model_name") or "",
        "endpoint": payload.get("endpoint") or "",
        "has_api_key": bool((payload.get("options") or {}).get("api_key")),
    }


class ModelConfigListView(APIView):
    """模型配置列表视图。

    GET  /api/model-configs/ — 列出所有模型配置及概览。
    POST /api/model-configs/ — 创建新的模型配置。
    需要 auth.manage_model_config 权限。
    """
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        """列出所有模型配置及概览数据。

        参数:
            request: Django REST Framework 的 Request 对象。
        返回:
            JSON 响应，包含 total、overview（总模型数/启用数/调用统计）、model_configs 列表。
        """
        _, permission_error = _require_manage_permission(request)
        if permission_error is not None:
            return permission_error

        model_configs = list_model_configs()
        overview = get_model_config_overview()
        return success_response(
            data={
                "total": model_configs.count(),
                "overview": overview,
                "model_configs": ModelConfigSummarySerializer(model_configs, many=True).data,
            }
        )

    def post(self, request):
        """创建新的模型配置。

        参数:
            request: Django REST Framework 的 Request 对象，body 包含模型配置各字段。
        返回:
            JSON 响应，包含新创建的 model_config 对象。
        """
        user, permission_error = _require_manage_permission(request)
        if permission_error is not None:
            return permission_error

        serializer = ModelConfigWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        model_config = create_model_config(payload=serializer.validated_data)
        record_audit_event(
            actor=user,
            action="llm.model_config.create",
            target_type="model_config",
            target_id=model_config.id,
            status=AuditRecord.STATUS_SUCCEEDED,
            detail_payload=_build_model_config_audit_payload(model_config),
        )
        return success_response(data={"model_config": ModelConfigSummarySerializer(model_config).data})


class ModelConfigDetailView(APIView):
    """模型配置详情视图。

    PATCH  /api/model-configs/<id>/ — 更新模型配置。
    DELETE /api/model-configs/<id>/ — 删除模型配置（启用中的不允许删除）。
    需要 auth.manage_model_config 权限。
    """
    authentication_classes = []
    permission_classes = []

    def patch(self, request, model_config_id):
        """更新指定模型配置。

        参数:
            request: Django REST Framework 的 Request 对象。
            model_config_id: URL 路径参数，模型配置的主键 ID。
        返回:
            JSON 响应，包含更新后的 model_config 对象。若配置不存在则返回 404。
        """
        user, permission_error = _require_manage_permission(request)
        if permission_error is not None:
            return permission_error

        model_config = get_model_config(model_config_id=model_config_id)
        if model_config is None:
            record_audit_event(
                actor=user,
                action="llm.model_config.update",
                target_type="model_config",
                target_id=model_config_id,
                status=AuditRecord.STATUS_FAILED,
                detail_payload={"error": "模型配置不存在。"},
            )
            return error_response(code=404, message="模型配置不存在。", status_code=404)

        serializer = ModelConfigWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        updated = update_model_config(model_config=model_config, payload=serializer.validated_data)
        record_audit_event(
            actor=user,
            action="llm.model_config.update",
            target_type="model_config",
            target_id=updated.id,
            status=AuditRecord.STATUS_SUCCEEDED,
            detail_payload=_build_model_config_audit_payload(updated),
        )
        return success_response(data={"model_config": ModelConfigSummarySerializer(updated).data})

    def delete(self, request, model_config_id):
        """删除指定模型配置。

        参数:
            request: Django REST Framework 的 Request 对象。
            model_config_id: URL 路径参数，模型配置的主键 ID。
        返回:
            JSON 响应，包含 {"deleted": True}。若配置不存在返回 404，配置启用中返回 400。
        """
        user, permission_error = _require_manage_permission(request)
        if permission_error is not None:
            return permission_error

        model_config = get_model_config(model_config_id=model_config_id)
        if model_config is None:
            record_audit_event(
                actor=user,
                action="llm.model_config.delete",
                target_type="model_config",
                target_id=model_config_id,
                status=AuditRecord.STATUS_FAILED,
                detail_payload={"error": "模型配置不存在。"},
            )
            return error_response(code=404, message="模型配置不存在。", status_code=404)

        model_payload = _build_model_config_audit_payload(model_config)
        try:
            delete_model_config(model_config=model_config)
        except ValueError as exc:
            record_audit_event(
                actor=user,
                action="llm.model_config.delete",
                target_type="model_config",
                target_id=model_config.id,
                status=AuditRecord.STATUS_FAILED,
                detail_payload={**model_payload, "error": str(exc)},
            )
            return error_response(code=400, message=str(exc), status_code=400)
        record_audit_event(
            actor=user,
            action="llm.model_config.delete",
            target_type="model_config",
            target_id=model_config_id,
            status=AuditRecord.STATUS_SUCCEEDED,
            detail_payload=model_payload,
        )
        return success_response(data={"deleted": True})


class ModelConfigActivationView(APIView):
    """模型配置启用/禁用视图。

    PATCH /api/model-configs/<id>/activation/ — 切换模型的启用状态。
    需要 auth.manage_model_config 权限。
    """
    authentication_classes = []
    permission_classes = []

    def patch(self, request, model_config_id):
        """切换指定模型配置的启用状态。

        参数:
            request: Django REST Framework 的 Request 对象，body 包含 {"is_active": bool}。
            model_config_id: URL 路径参数，模型配置的主键 ID。
        返回:
            JSON 响应，包含更新后的 model_config 对象。若配置不存在则返回 404。
        """
        user, permission_error = _require_manage_permission(request)
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
            record_audit_event(
                actor=user,
                action="llm.model_config.set_active_state",
                target_type="model_config",
                target_id=model_config_id,
                status=AuditRecord.STATUS_FAILED,
                detail_payload={"is_active": serializer.validated_data["is_active"], "error": "模型配置不存在。"},
            )
            return error_response(code=404, message="模型配置不存在。", status_code=404)

        record_audit_event(
            actor=user,
            action="llm.model_config.set_active_state",
            target_type="model_config",
            target_id=model_config.id,
            status=AuditRecord.STATUS_SUCCEEDED,
            detail_payload=_build_model_config_audit_payload(model_config),
        )
        return success_response(
            data={"model_config": ModelConfigSummarySerializer(model_config).data}
        )


class ModelConfigConnectionTestView(APIView):
    """模型连接测试视图。

    POST /api/model-configs/test-connection/ — 发送一次测试调用验证 API 端点是否可达。
    支持 chat、embedding、rerank 三种能力类型的连接测试。
    需要 auth.manage_model_config 权限。
    """
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        """测试模型配置的连接是否可达。

        参数:
            request: Django REST Framework 的 Request 对象，body 包含 provider、model_name、endpoint、
                     options 等信息。
        返回:
            JSON 响应，包含 {"ok": True} 表示连接成功。
            若配置无效返回 400，服务不可用返回 503，上游错误返回对应状态码。
        """
        user, permission_error = _require_manage_permission(request)
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
        except ValueError as exc:
            record_audit_event(
                actor=user,
                action="llm.model_config.test_connection",
                target_type="model_config",
                target_id=payload.get("model_config_id") or "",
                status=AuditRecord.STATUS_FAILED,
                detail_payload={**_build_model_config_test_payload(payload), "error": str(exc)},
            )
            return error_response(code=400, message=str(exc), status_code=400)
        except ServiceConfigurationError as exc:
            record_audit_event(
                actor=user,
                action="llm.model_config.test_connection",
                target_type="model_config",
                target_id=payload.get("model_config_id") or "",
                status=AuditRecord.STATUS_FAILED,
                detail_payload={**_build_model_config_test_payload(payload), "error": exc.message},
            )
            return error_response(code=503, message=exc.message, status_code=503, data={"error": exc.code})
        except UpstreamServiceError as exc:
            record_audit_event(
                actor=user,
                action="llm.model_config.test_connection",
                target_type="model_config",
                target_id=payload.get("model_config_id") or "",
                status=AuditRecord.STATUS_FAILED,
                detail_payload={**_build_model_config_test_payload(payload), "error": exc.message},
            )
            return error_response(code=exc.status_code, message=exc.message, status_code=exc.status_code, data={"error": exc.code})
        record_audit_event(
            actor=user,
            action="llm.model_config.test_connection",
            target_type="model_config",
            target_id=payload.get("model_config_id") or "",
            status=AuditRecord.STATUS_SUCCEEDED,
            detail_payload=_build_model_config_test_payload(payload),
        )
        return success_response(data=result)
