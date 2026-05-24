"""
风险事件列表控制器 —— GET /api/risk/events
类比 SpringBoot: 相当于 @RestController 中的 @GetMapping 方法，
支持按公司、风险类型、审核状态、风险级别、文档 ID、时间范围等多维过滤。
"""

from rest_framework.views import APIView

from common.api_response import error_response, success_response
from rbac.services.authz_service import get_authenticated_user, user_has_permission
from risk.serializers import RiskEventListQuerySerializer, RiskEventSummarySerializer
from risk.services.query_service import list_risk_events


class RiskEventListView(APIView):
    """
    风险事件列表视图 —— 返回过滤后的风险事件列表。

    类比 SpringBoot: 相当于 @RestController + @GetMapping("/events")。
    """
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        """
        获取风险事件列表（支持多条件过滤）。

        参数:
            request: Django HttpRequest，查询参数支持:
                     - company_name (str, 可选): 公司名称（模糊匹配）
                     - risk_type    (str, 可选): 风险类型（模糊匹配）
                     - review_status (str, 可选): 审核状态
                     - risk_level   (str, 可选): 风险级别
                     - document_id  (int, 可选): 文档 ID
                     - period_start (date, 可选): 事件时间范围起点
                     - period_end   (date, 可选): 事件时间范围终点

        返回:
            JsonResponse: 包含 total 和 risk_events 数组的数据。
        """
        user = get_authenticated_user(request)
        if user is None:
            return error_response(code=401, message="未认证。", status_code=401)
        if not user_has_permission(user, "auth.view_document"):
            return error_response(code=403, message="无权限。", status_code=403)

        serializer = RiskEventListQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)

        risk_events = list(list_risk_events(filters=serializer.validated_data))
        return success_response(
            data={
                "total": len(risk_events),
                "risk_events": RiskEventSummarySerializer(risk_events, many=True).data,
            }
        )
