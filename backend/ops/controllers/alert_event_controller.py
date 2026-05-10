from rest_framework.views import APIView

from common.api_response import error_response, success_response
from ops.services import acknowledge_event, list_alert_events
from rbac.services.authz_service import get_authenticated_user, user_has_permission


def _require_view_permission(request):
    user = get_authenticated_user(request)
    if user is None:
        return None, error_response(code=401, message="未认证。", status_code=401)
    if not user_has_permission(user, "auth.view_monitoring"):
        return None, error_response(code=403, message="无权限。", status_code=403)
    return user, None


def _require_ack_permission(request):
    user = get_authenticated_user(request)
    if user is None:
        return None, error_response(code=401, message="未认证。", status_code=401)
    if not user_has_permission(user, "auth.acknowledge_alerts"):
        return None, error_response(code=403, message="无权限。", status_code=403)
    return user, None


class AlertEventListView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        _, permission_error = _require_view_permission(request)
        if permission_error is not None:
            return permission_error

        status = request.query_params.get("status")
        limit = int(request.query_params.get("limit", 50))
        data = list_alert_events(status=status, limit=limit)
        return success_response(data=data)


class AlertEventAcknowledgeView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request, event_id):
        user, permission_error = _require_ack_permission(request)
        if permission_error is not None:
            return permission_error

        try:
            data = acknowledge_event(event_id=event_id, user=user)
            return success_response(data=data)
        except Exception as exc:
            return error_response(code=400, message=str(exc), status_code=400)
