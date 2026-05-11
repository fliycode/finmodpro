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
    user = get_authenticated_user(request)
    if user is None:
        return None, error_response(code=401, message="未认证。", status_code=401)
    if not user_has_permission(user, "auth.manage_model_config"):
        return None, error_response(code=403, message="无权限。", status_code=403)
    return user, None


def _build_model_config_audit_payload(model_config):
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
    return {
        "model_config_id": payload.get("model_config_id") or "",
        "capability": payload.get("capability") or "",
        "provider": payload.get("provider") or "",
        "model_name": payload.get("model_name") or "",
        "endpoint": payload.get("endpoint") or "",
        "has_api_key": bool((payload.get("options") or {}).get("api_key")),
    }


class ModelConfigListView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
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
    authentication_classes = []
    permission_classes = []

    def patch(self, request, model_config_id):
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
    authentication_classes = []
    permission_classes = []

    def patch(self, request, model_config_id):
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
    authentication_classes = []
    permission_classes = []

    def post(self, request):
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
