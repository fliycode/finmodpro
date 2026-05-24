"""
风险分析概览控制器 —— GET /api/risk/analytics/overview
类比 SpringBoot: 相当于 @RestController 中的 @GetMapping 方法，
返回风险事件的多维度分析数据（总量、分布、趋势、Top 公司）。
"""

from rest_framework.views import APIView

from common.api_response import error_response, success_response
from rbac.services.authz_service import get_authenticated_user, user_has_permission
from risk.serializers import RiskEventListQuerySerializer
from risk.services.analytics_service import build_risk_analytics_overview


class RiskAnalyticsOverviewView(APIView):
    """
    风险分析概览视图 —— 返回聚合的风险分析仪表盘数据。

    类比 SpringBoot: 相当于 @RestController + @GetMapping("/analytics/overview")。
    """
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        """
        获取风险分析概览数据。

        参数:
            request: Django HttpRequest，查询参数支持与事件列表相同的过滤条件。

        返回:
            JsonResponse: 包含 summary（关键指标）、分布（risk_level/risk_type/review_status）、
                         trend（时间趋势）和 top_companies（高频公司）的数据。
        """
        user = get_authenticated_user(request)
        if user is None:
            return error_response(code=401, message="未认证。", status_code=401)
        if not user_has_permission(user, "auth.view_document"):
            return error_response(code=403, message="无权限。", status_code=403)

        serializer = RiskEventListQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)

        return success_response(data=build_risk_analytics_overview(filters=serializer.validated_data))
