from rest_framework.views import APIView

from common.api_response import error_response, success_response
from common.exceptions import ServiceConfigurationError, UpstreamServiceError
from llm.controllers.model_config_controller import _require_manage_permission
from llm.services.lightrag_compat_service import build_lightrag_compat_overview, handle_lightrag_compat_request
from llm.services.lightrag_proxy_service import (
    build_lightrag_overview,
    proxy_lightrag_request,
    use_compat_backend,
)


def _get_payload(request):
    if request.content_type and "application/json" in request.content_type:
        return request.data
    return None


def _handle_proxy(method, request, upstream_path):
    user, permission_error = _require_manage_permission(request)
    if permission_error is not None:
        return permission_error

    try:
        if use_compat_backend():
            payload = handle_lightrag_compat_request(
                user=user,
                method=method,
                upstream_path=upstream_path,
                query_params=request.query_params,
                json_payload=_get_payload(request),
                request_data=request.data,
                request_files=request.FILES,
            )
        else:
            payload = proxy_lightrag_request(
                method=method,
                upstream_path=upstream_path,
                query_params=request.query_params,
                json_payload=_get_payload(request),
                request_data=request.data,
                request_files=request.FILES,
            )
    except ValueError:
        return error_response(code=404, message="不支持的 LightRAG 路径。", status_code=404)
    except ServiceConfigurationError as exc:
        return error_response(code=503, message=exc.message, status_code=503, data={"error": exc.code})
    except UpstreamServiceError as exc:
        return error_response(
            code=exc.status_code,
            message=exc.message,
            status_code=exc.status_code,
            data={"error": exc.code},
        )
    return success_response(data=payload)


class LightragOverviewView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        user, permission_error = _require_manage_permission(request)
        if permission_error is not None:
            return permission_error
        try:
            if use_compat_backend():
                return success_response(data=build_lightrag_compat_overview(user))
            return success_response(data=build_lightrag_overview())
        except ServiceConfigurationError as exc:
            return error_response(code=503, message=exc.message, status_code=503, data={"error": exc.code})
        except UpstreamServiceError as exc:
            return error_response(
                code=exc.status_code,
                message=exc.message,
                status_code=exc.status_code,
                data={"error": exc.code},
            )


class LightragProxyView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request, upstream_path):
        return _handle_proxy("GET", request, upstream_path)

    def post(self, request, upstream_path):
        return _handle_proxy("POST", request, upstream_path)

    def delete(self, request, upstream_path):
        return _handle_proxy("DELETE", request, upstream_path)
