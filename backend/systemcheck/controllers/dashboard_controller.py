"""
管理仪表盘控制器 —— 提供系统概览统计数据。

类比 SpringBoot: 相当于 Spring Admin 的 /dashboard/stats 端点，
返回知识库、风险、模型调用、审计等全系统关键指标的聚合数据。
"""

from rest_framework.views import APIView

from common.api_response import error_response, success_response
from rbac.services.authz_service import get_authenticated_user, user_has_permission
from systemcheck.services import get_dashboard_stats


class DashboardStatsView(APIView):
    """
    管理仪表盘统计视图 —— GET /api/systemcheck/dashboard/stats

    返回系统全局概览数据，包括文档统计、风险事件统计、模型调用量、
    Token 消耗、聊天请求、检索命中率、审计操作和最近活动等。

    类比 SpringBoot: 相当于 @GetMapping("/dashboard/stats") + Actuator 指标聚合。
    """
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        """
        获取系统仪表盘统计数据。

        参数:
            request: Django HttpRequest。

        返回:
            JsonResponse: 包含 knowledgebase_count, document_count, risk_event_count,
                         model_invocation_count_7d, token_count_7d, audit_operations_7d,
                         retrieval_hit_rate, risk_level_distribution 等全面的统计数据。
                         未认证: 401, 无权限: 403
        """
        user = get_authenticated_user(request)
        if user is None:
            return error_response(code=401, message="未认证。", status_code=401)
        if not user_has_permission(user, "auth.view_dashboard"):
            return error_response(code=403, message="无权限。", status_code=403)

        return success_response(data=get_dashboard_stats())
