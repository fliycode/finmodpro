"""
风险报告控制器 —— 处理风险报告的生成与导出。
类比 SpringBoot: 相当于 @RestController 中的 @PostMapping / @GetMapping 方法，
支持公司/文档/时间区间三种维度的报告生成，以及 Markdown/JSON 格式的导出。
"""

from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView

from common.api_response import error_response, success_response
from knowledgebase.models import Document
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
    generate_document_risk_report,
    generate_time_range_risk_report,
)


def _build_validation_error_response(errors):
    """
    构造参数校验错误的响应。

    参数:
        errors (dict): Serializer 的 errors 字典。

    返回:
        JsonResponse: 包含错误信息的 400 响应。
    """
    message_errors = errors.get("message")
    message = str(message_errors[0]) if message_errors else "请求失败。"
    return error_response(code=400, message=message, data=errors, status_code=400)


class CompanyRiskReportCreateView(APIView):
    """
    公司风险报告生成视图 —— POST /api/risk/reports/company

    类比 SpringBoot: 相当于 @PostMapping("/reports/company")。
    """
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        """
        生成指定公司的风险报告。

        参数:
            request: Django HttpRequest，body 包含:
                     - company_name (str, 必填): 公司名称
                     - period_start (date, 可选): 时间起始
                     - period_end   (date, 可选): 时间结束

        返回:
            JsonResponse: 201 成功时包含生成的报告数据。
        """
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


class DocumentRiskReportCreateView(APIView):
    """
    文档风险报告生成视图 —— POST /api/risk/documents/{document_id}/report

    类比 SpringBoot: 相当于 @PostMapping("/documents/{documentId}/report")。
    """
    authentication_classes = []
    permission_classes = []

    def post(self, request, document_id):
        """
        生成指定文档的风险报告。

        参数:
            request: Django HttpRequest。
            document_id (int): 路径参数，文档 ID。

        返回:
            JsonResponse: 201 成功时包含生成的报告数据。
        """
        user = get_authenticated_user(request)
        if user is None:
            return error_response(code=401, message="未认证。", status_code=401)
        if not user_has_permission(user, "auth.view_document"):
            return error_response(code=403, message="无权限。", status_code=403)

        document = get_object_or_404(Document, id=document_id)

        try:
            report = generate_document_risk_report(document=document)
        except RiskEvent.DoesNotExist:
            return error_response(code=404, message="当前文档暂无可生成报告的风险事件。", status_code=404)

        return success_response(
            message="文档风险报告生成完成。",
            data={"report": RiskReportSerializer(report).data},
            status_code=201,
        )


class TimeRangeRiskReportCreateView(APIView):
    """
    时间区间风险报告生成视图 —— POST /api/risk/reports/time-range

    类比 SpringBoot: 相当于 @PostMapping("/reports/time-range")。
    """
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        """
        生成指定时间区间的风险报告。

        参数:
            request: Django HttpRequest，body 包含:
                     - period_start (date, 必填): 起始日期
                     - period_end   (date, 必填): 结束日期

        返回:
            JsonResponse: 201 成功时包含生成的报告数据。
        """
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
    """
    风险报告导出视图 —— GET /api/risk/reports/{report_id}/export?format=markdown

    类比 SpringBoot: 相当于 @GetMapping("/reports/{reportId}/export")。
    """
    authentication_classes = []
    permission_classes = []

    def get(self, request, report_id):
        """
        导出指定风险报告为文件（Markdown 或 JSON 格式）。

        参数:
            request: Django HttpRequest。
                    查询参数:
                    - format (str, 可选, 默认 "markdown"): 导出格式（markdown 或 json）
            report_id (int): 路径参数，报告 ID。

        返回:
            HttpResponse: 包含文件内容的下载响应。
        """
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
