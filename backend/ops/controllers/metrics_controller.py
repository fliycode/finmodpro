"""
指标控制器 —— 处理系统监控指标相关的请求。
类比 SpringBoot: 相当于 @RestController 中的监控端点，
提供系统状态概览和指标时序数据查询。
"""

from rest_framework.views import APIView

from common.api_response import error_response, success_response
from ops.services import get_current_system_status, get_metric_time_series
from rbac.services.authz_service import get_authenticated_user, user_has_permission


def _require_view_permission(request):
    """
    检查用户是否具有查看监控 (auth.view_monitoring) 权限。

    类比 SpringBoot: 相当于 @PreAuthorize("hasAuthority('auth.view_monitoring')") 注解。

    参数:
        request: Django HttpRequest 对象。

    返回:
        tuple: (user, error_response | None)
    """
    user = get_authenticated_user(request)
    if user is None:
        return None, error_response(code=401, message="未认证。", status_code=401)
    if not user_has_permission(user, "auth.view_monitoring"):
        return None, error_response(code=403, message="无权限。", status_code=403)
    return user, None


class SystemStatusView(APIView):
    """
    系统状态视图 —— GET /api/ops/monitoring/status

    返回当前系统的整体健康状态，包括各关键指标的最新值和活跃告警数。

    类比 SpringBoot: 相当于 Spring Actuator 的 /health 端点。
    """
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        """
        获取系统当前状态概览。

        参数:
            request: Django HttpRequest。

        返回:
            JsonResponse: 包含 metrics（各指标最新值）和 firing_alerts（活跃告警数）的数据。
        """
        _, permission_error = _require_view_permission(request)
        if permission_error is not None:
            return permission_error
        data = get_current_system_status()
        return success_response(data=data)


class MetricTimeSeriesView(APIView):
    """
    指标时序数据视图 —— GET /api/ops/monitoring/metrics?metric_name=xxx&hours=24

    返回指定指标在指定时间范围内的历史数据点。

    类比 SpringBoot: 相当于 Prometheus 的 /api/v1/query_range 端点。
    """
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        """
        获取指标时序数据。

        参数:
            request: Django HttpRequest。
                    查询参数:
                    - metric_name (str, 必填): 指标名称
                    - hours       (int, 可选, 默认 24): 向前查询的小时数

        返回:
            JsonResponse: 包含 metric_name, hours 和 data_points 数组的数据。
        """
        _, permission_error = _require_view_permission(request)
        if permission_error is not None:
            return permission_error

        metric_name = request.query_params.get("metric_name", "")
        if not metric_name:
            return error_response(code=400, message="缺少 metric_name 参数。", status_code=400)

        hours = int(request.query_params.get("hours", 24))
        data = get_metric_time_series(metric_name=metric_name, hours=hours)
        return success_response(data=data)
