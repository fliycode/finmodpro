from rest_framework.views import APIView

from common.api_response import error_response, success_response
from ops.services import get_current_system_status, get_metric_time_series
from rbac.services.authz_service import get_authenticated_user, user_has_permission


def _require_view_permission(request):
    user = get_authenticated_user(request)
    if user is None:
        return None, error_response(code=401, message="未认证。", status_code=401)
    if not user_has_permission(user, "auth.view_monitoring"):
        return None, error_response(code=403, message="无权限。", status_code=403)
    return user, None


class SystemStatusView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        _, permission_error = _require_view_permission(request)
        if permission_error is not None:
            return permission_error
        data = get_current_system_status()
        return success_response(data=data)


class MetricTimeSeriesView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        _, permission_error = _require_view_permission(request)
        if permission_error is not None:
            return permission_error

        metric_name = request.query_params.get("metric_name", "")
        if not metric_name:
            return error_response(code=400, message="缺少 metric_name 参数。", status_code=400)

        hours = int(request.query_params.get("hours", 24))
        data = get_metric_time_series(metric_name=metric_name, hours=hours)
        return success_response(data=data)
