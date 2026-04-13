from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView

from common.api_response import error_response, success_response
from rbac.services.authz_service import get_authenticated_user, user_has_permission
from risk.models import RiskEvent, RiskReport
from risk.serializers import (
    CompanyRiskReportCreateSerializer,
    RiskReportSerializer,
    TimeRangeRiskReportCreateSerializer,
)
from risk.services.report_service import (
    build_risk_report_export,
    generate_company_risk_report,
    generate_time_range_risk_report,
)


def _build_validation_error_response(errors):
    message_errors = errors.get("message")
    message = str(message_errors[0]) if message_errors else "请求失败。"
    return error_response(code=400, message=message, data=errors, status_code=400)


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
        if not serializer.is_valid():
            return _build_validation_error_response(serializer.errors)

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


class TimeRangeRiskReportCreateView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        user = get_authenticated_user(request)
        if user is None:
            return error_response(code=401, message="未认证。", status_code=401)
        if not user_has_permission(user, "auth.view_document"):
            return error_response(code=403, message="无权限。", status_code=403)

        serializer = TimeRangeRiskReportCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return _build_validation_error_response(serializer.errors)

        try:
            report = generate_time_range_risk_report(
                period_start=serializer.validated_data["period_start"],
                period_end=serializer.validated_data["period_end"],
            )
        except RiskEvent.DoesNotExist:
            return error_response(code=404, message="未找到已审核通过的风险事件。", status_code=404)

        return success_response(
            message="时间区间风险报告生成完成。",
            data={"report": RiskReportSerializer(report).data},
            status_code=201,
        )


class RiskReportExportView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request, report_id):
        user = get_authenticated_user(request)
        if user is None:
            return error_response(code=401, message="未认证。", status_code=401)
        if not user_has_permission(user, "auth.view_document"):
            return error_response(code=403, message="无权限。", status_code=403)

        report = get_object_or_404(RiskReport, id=report_id)
        export_format = request.query_params.get("format", "markdown")

        try:
            payload = build_risk_report_export(report=report, export_format=export_format)
        except ValueError as exc:
            return error_response(code=400, message=str(exc), status_code=400)

        response = HttpResponse(payload["content"], content_type=f'{payload["content_type"]}; charset=utf-8')
        response["Content-Disposition"] = f'attachment; filename="{payload["filename"]}"'
        return response
