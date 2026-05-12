from rest_framework.views import APIView

from common.api_response import error_response, success_response
from ops.services import (
    create_alert_rule,
    delete_alert_rule,
    get_alert_rule,
    list_alert_rules,
    seed_default_alert_rules,
    update_alert_rule,
)
from rbac.services.authz_service import get_authenticated_user, user_has_permission


def _require_manage_permission(request):
    user = get_authenticated_user(request)
    if user is None:
        return None, error_response(code=401, message="未认证。", status_code=401)
    if not user_has_permission(user, "auth.manage_alert_rules"):
        return None, error_response(code=403, message="无权限。", status_code=403)
    return user, None


class AlertRuleListView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        _, permission_error = _require_manage_permission(request)
        if permission_error is not None:
            return permission_error

        enabled_only = request.query_params.get("enabled_only") == "true"
        data = list_alert_rules(enabled_only=enabled_only)
        return success_response(data=data)

    def post(self, request):
        user, permission_error = _require_manage_permission(request)
        if permission_error is not None:
            return permission_error

        body = request.data or {}
        name = body.get("name", "").strip()
        metric_name = body.get("metric_name", "").strip()
        condition = body.get("condition", "").strip()
        threshold = body.get("threshold")

        if not name or not metric_name or not condition or threshold is None:
            return error_response(
                code=400,
                message="缺少必填字段: name, metric_name, condition, threshold。",
                status_code=400,
            )

        try:
            data = create_alert_rule(
                name=name,
                metric_name=metric_name,
                condition=condition,
                threshold=float(threshold),
                severity=body.get("severity", "warning"),
                enabled=body.get("enabled", True),
                notification_channels=body.get("notification_channels", []),
                description=body.get("description", ""),
                created_by=user,
            )
            return success_response(data=data, status_code=201)
        except Exception as exc:
            return error_response(code=400, message=str(exc), status_code=400)


class AlertRuleDetailView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request, rule_id):
        _, permission_error = _require_manage_permission(request)
        if permission_error is not None:
            return permission_error

        data = get_alert_rule(rule_id=rule_id)
        if data is None:
            return error_response(code=404, message="告警规则不存在。", status_code=404)
        return success_response(data=data)

    def patch(self, request, rule_id):
        _, permission_error = _require_manage_permission(request)
        if permission_error is not None:
            return permission_error

        from ops.models import AlertRule

        try:
            rule = AlertRule.objects.get(id=rule_id)
        except AlertRule.DoesNotExist:
            return error_response(code=404, message="告警规则不存在。", status_code=404)

        body = request.data or {}
        kwargs = {}
        for field in ("name", "metric_name", "condition", "severity", "enabled", "notification_channels", "description"):
            if field in body:
                kwargs[field] = body[field]
        if "threshold" in body:
            kwargs["threshold"] = float(body["threshold"])

        try:
            data = update_alert_rule(rule=rule, **kwargs)
            return success_response(data=data)
        except Exception as exc:
            return error_response(code=400, message=str(exc), status_code=400)

    def delete(self, request, rule_id):
        _, permission_error = _require_manage_permission(request)
        if permission_error is not None:
            return permission_error

        from ops.models import AlertRule

        try:
            rule = AlertRule.objects.get(id=rule_id)
        except AlertRule.DoesNotExist:
            return error_response(code=404, message="告警规则不存在。", status_code=404)

        delete_alert_rule(rule=rule)
        return success_response(data={"deleted": True})


class AlertRuleSeedDefaultsView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        user, permission_error = _require_manage_permission(request)
        if permission_error is not None:
            return permission_error

        result = seed_default_alert_rules(created_by=user)
        status_code = 201 if result["created"] else 200
        return success_response(data=result, status_code=status_code)
