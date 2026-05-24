"""
告警规则控制器 —— 处理告警规则的完整 CRUD 操作。
类比 SpringBoot: 相当于 @RestController + @RequestMapping("/alerts/rules")，
提供规则的列表、创建、详情、更新、删除和默认规则播种等功能。
"""

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
    """
    检查用户是否具有管理告警规则 (auth.manage_alert_rules) 权限。

    类比 SpringBoot: 相当于 @PreAuthorize("hasAuthority('auth.manage_alert_rules')") 注解。

    参数:
        request: Django HttpRequest 对象。

    返回:
        tuple: (user, error_response | None)
    """
    user = get_authenticated_user(request)
    if user is None:
        return None, error_response(code=401, message="未认证。", status_code=401)
    if not user_has_permission(user, "auth.manage_alert_rules"):
        return None, error_response(code=403, message="无权限。", status_code=403)
    return user, None


class AlertRuleListView(APIView):
    """
    告警规则列表视图 —— GET/POST /api/ops/alerts/rules

    类比 SpringBoot: 相当于 @RestController + @RequestMapping("/alerts/rules")
    """
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        """
        获取告警规则列表。

        参数:
            request: Django HttpRequest。
                    查询参数:
                    - enabled_only (str, 可选): "true" 则仅返回启用的规则。

        返回:
            JsonResponse: 包含规则数组的成功响应。
        """
        _, permission_error = _require_manage_permission(request)
        if permission_error is not None:
            return permission_error

        enabled_only = request.query_params.get("enabled_only") == "true"
        data = list_alert_rules(enabled_only=enabled_only)
        return success_response(data=data)

    def post(self, request):
        """
        创建新的告警规则。

        参数:
            request: Django HttpRequest，body 包含:
                     - name (str, 必填): 规则名称
                     - metric_name (str, 必填): 监控指标名称
                     - condition (str, 必填): 比较条件
                     - threshold (float, 必填): 阈值
                     - severity (str, 可选): 严重级别，默认 "warning"
                     - enabled (bool, 可选): 是否启用，默认 True
                     - notification_channels (list, 可选): 通知渠道
                     - description (str, 可选): 规则描述

        返回:
            JsonResponse: 201 成功时包含新创建的规则数据。
        """
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
    """
    单条告警规则详情视图 —— GET/PATCH/DELETE /api/ops/alerts/rules/{rule_id}

    类比 SpringBoot: 相当于 @RestController + @RequestMapping("/alerts/rules/{ruleId}")
    """
    authentication_classes = []
    permission_classes = []

    def get(self, request, rule_id):
        """
        获取单条告警规则的详情。

        参数:
            request: Django HttpRequest。
            rule_id (int): 路径参数，告警规则 ID。

        返回:
            JsonResponse: 规则详情数据，或 404 错误。
        """
        _, permission_error = _require_manage_permission(request)
        if permission_error is not None:
            return permission_error

        data = get_alert_rule(rule_id=rule_id)
        if data is None:
            return error_response(code=404, message="告警规则不存在。", status_code=404)
        return success_response(data=data)

    def patch(self, request, rule_id):
        """
        部分更新告警规则（只更新请求 body 中提供的字段）。

        参数:
            request: Django HttpRequest，body 包含要更新的字段。
            rule_id (int): 路径参数，告警规则 ID。

        返回:
            JsonResponse: 更新后的规则数据。
        """
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
        """
        删除指定的告警规则。

        参数:
            request: Django HttpRequest。
            rule_id (int): 路径参数，要删除的告警规则 ID。

        返回:
            JsonResponse: {"deleted": true}
        """
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
    """
    播种默认告警规则视图 —— POST /api/ops/alerts/rules/seed-defaults

    创建系统预定义的默认告警规则（如 CPU 过高、内存过高等），
    如果规则已存在则跳过。

    类比 SpringBoot: 相当于 @PostMapping("/seed-defaults") 的初始化端点。
    """
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        """
        播种（创建）默认告警规则。

        参数:
            request: Django HttpRequest。

        返回:
            JsonResponse: 包含 created（新创建数）、skipped（跳过数）和 rules 列表。
                         状态码 201（有新创建）或 200（全部已存在）。
        """
        user, permission_error = _require_manage_permission(request)
        if permission_error is not None:
            return permission_error

        result = seed_default_alert_rules(created_by=user)
        status_code = 201 if result["created"] else 200
        return success_response(data=result, status_code=status_code)
