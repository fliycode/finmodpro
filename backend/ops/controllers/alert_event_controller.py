"""
告警事件控制器 —— 处理告警事件的查看和确认。
类比 SpringBoot: 相当于 @RestController 中的 @GetMapping / @PostMapping 方法，
负责接收 HTTP 请求、校验权限、调用 Service 层、构造 HTTP 响应。
"""

from rest_framework.views import APIView

from common.api_response import error_response, success_response
from ops.services import acknowledge_event, list_alert_events
from rbac.services.authz_service import get_authenticated_user, user_has_permission


def _require_view_permission(request):
    """
    检查用户是否具有查看监控 (auth.view_monitoring) 权限。

    类比 SpringBoot: 相当于 @PreAuthorize("hasAuthority('auth.view_monitoring')") 注解。

    参数:
        request: Django HttpRequest 对象。

    返回:
        tuple: (user, error_response | None)
               - 认证通过: (user, None)
               - 未认证:   (None, 401 错误响应)
               - 无权限:   (None, 403 错误响应)
    """
    user = get_authenticated_user(request)
    if user is None:
        return None, error_response(code=401, message="未认证。", status_code=401)
    if not user_has_permission(user, "auth.view_monitoring"):
        return None, error_response(code=403, message="无权限。", status_code=403)
    return user, None


def _require_ack_permission(request):
    """
    检查用户是否具有确认告警 (auth.acknowledge_alerts) 权限。

    类比 SpringBoot: 相当于 @PreAuthorize("hasAuthority('auth.acknowledge_alerts')") 注解。

    参数:
        request: Django HttpRequest 对象。

    返回:
        tuple: (user, error_response | None)
    """
    user = get_authenticated_user(request)
    if user is None:
        return None, error_response(code=401, message="未认证。", status_code=401)
    if not user_has_permission(user, "auth.acknowledge_alerts"):
        return None, error_response(code=403, message="无权限。", status_code=403)
    return user, None


class AlertEventListView(APIView):
    """
    告警事件列表视图 —— GET /api/ops/alerts/events

    返回告警事件列表，支持按状态过滤。

    类比 SpringBoot: 相当于 @RestController 类，每个方法对应一个端点。
    """
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        """
        获取告警事件列表。

        参数:
            request: Django HttpRequest。
                    查询参数:
                    - status (str, 可选): 过滤状态 (firing / resolved / acknowledged)
                    - limit  (int, 可选, 默认 50): 返回的最大事件数量

        返回:
            JsonResponse: 包含 events 数组的成功响应。
        """
        _, permission_error = _require_view_permission(request)
        if permission_error is not None:
            return permission_error

        status = request.query_params.get("status")
        limit = int(request.query_params.get("limit", 50))
        data = list_alert_events(status=status, limit=limit)
        return success_response(data=data)


class AlertEventAcknowledgeView(APIView):
    """
    告警事件确认视图 —— POST /api/ops/alerts/events/{event_id}/acknowledge

    将状态为 firing 的告警事件标记为已确认。

    类比 SpringBoot: 相当于 @PostMapping("/{eventId}/acknowledge")
    """
    authentication_classes = []
    permission_classes = []

    def post(self, request, event_id):
        """
        确认指定的告警事件。

        参数:
            request: Django HttpRequest。
            event_id (int): 路径参数，告警事件 ID。

        返回:
            JsonResponse: 确认后的告警事件数据，或错误信息。
        """
        user, permission_error = _require_ack_permission(request)
        if permission_error is not None:
            return permission_error

        try:
            data = acknowledge_event(event_id=event_id, user=user)
            return success_response(data=data)
        except Exception as exc:
            return error_response(code=400, message=str(exc), status_code=400)
