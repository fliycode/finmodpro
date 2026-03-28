from rest_framework.views import APIView

from common.api_response import error_response, success_response
from rbac.services.authz_service import get_authenticated_user, user_has_permission
from risk.models import RiskEvent
from risk.serializers import CompanyRiskReportCreateSerializer, RiskReportSerializer
from risk.services.report_service import generate_company_risk_report


class CompanyRiskReportCreateView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        user = get_authenticated_user(request)
        if user is None:
            return error_response(code=401, message="未认证。", status_code=401)
        if not user_has_permission(user, "auth.view_document"):
            return error_response(code=403, message="无权限。", status_code=403)

        serializer = CompanyRiskReportCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            report = generate_company_risk_report(
                company_name=serializer.validated_data["company_name"],
                period_start=serializer.validated_data.get("period_start"),
                period_end=serializer.validated_data.get("period_end"),
            )
        except RiskEvent.DoesNotExist:
            return error_response(code=404, message="未找到已审核通过的风险事件。", status_code=404)

        return success_response(
            message="公司风险报告生成完成。",
            data={"report": RiskReportSerializer(report).data},
            status_code=201,
        )
