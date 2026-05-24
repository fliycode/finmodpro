"""
网关监控控制器（类比 SpringBoot 中 @RestController）。
提供 LLM 网关的分析面 API，包括概览、日志、追踪、错误和成本统计。
所有端点均需要 auth.manage_model_config 权限。
"""
from rest_framework.views import APIView

from common.api_response import error_response, success_response
from llm.controllers.model_config_controller import _require_manage_permission
from llm.services.model_usage_query_service import (
    get_costs_models,
    get_costs_summary,
    get_costs_timeseries,
    get_errors,
    get_gateway_summary,
    get_logs,
    get_logs_summary,
    get_trace,
)


def _parse_query_filters(request) -> dict:
    """从请求查询参数中解析通用筛选条件。

    参数:
        request: Django REST Framework 的 Request 对象。
    返回:
        dict，包含 model（模型别名筛选）、status（状态筛选）、time（时间窗口预设）三个键。
    """
    return {
        "model": request.query_params.get("model") or None,
        "status": request.query_params.get("status") or None,
        "time": request.query_params.get("time") or "24h",
    }


class GatewaySummaryView(APIView):
    """网关概览视图。

    GET /api/llm/gateway/summary/ — 返回网关健康状态、活跃模型数、24h 流量统计和 Top 模型排名。
    """
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        """获取网关概览数据。

        参数:
            request: Django REST Framework 的 Request 对象。
        返回:
            JSON 响应，包含 gateway（状态）、traffic（请求量/失败数/错误率）、top_models、recent_errors。
        """
        _, permission_error = _require_manage_permission(request)
        if permission_error is not None:
            return permission_error
        return success_response(data=get_gateway_summary())


class GatewayLogsView(APIView):
    """网关日志视图。

    GET /api/llm/gateway/logs/ — 返回分页的调用日志列表，支持 model/status/time 筛选。
    """
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        """获取分页的调用日志列表。

        参数:
            request: Django REST Framework 的 Request 对象，支持 query params：
                     model（模型别名）、status（状态）、time（时间窗口）、page（页码）、page_size（每页条数）。
        返回:
            JSON 响应，包含 total、page、page_size 和 logs 列表。
        """
        _, permission_error = _require_manage_permission(request)
        if permission_error is not None:
            return permission_error
        filters = _parse_query_filters(request)
        try:
            page = max(1, int(request.query_params.get("page", 1)))
        except (ValueError, TypeError):
            page = 1
        try:
            page_size = max(1, min(200, int(request.query_params.get("page_size", 50))))
        except (ValueError, TypeError):
            page_size = 50
        return success_response(data=get_logs(filters, page=page, page_size=page_size))


class GatewayLogsSummaryView(APIView):
    """网关日志摘要视图。

    GET /api/llm/gateway/logs/summary/ — 返回日志聚合指标：请求总量、错误率、延迟分桶、错误码分布。
    """
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        """获取日志聚合摘要。

        参数:
            request: Django REST Framework 的 Request 对象，支持 model/status/time 筛选参数。
        返回:
            JSON 响应，包含 total_requests、error_rate_pct、avg_latency_ms、error_breakdown、latency_buckets。
        """
        _, permission_error = _require_manage_permission(request)
        if permission_error is not None:
            return permission_error
        filters = _parse_query_filters(request)
        return success_response(data=get_logs_summary(filters))


class GatewayTraceView(APIView):
    """网关链路追踪视图。

    GET /api/llm/gateway/traces/<trace_id>/ — 返回指定 trace_id 下的所有调用日志。
    """
    authentication_classes = []
    permission_classes = []

    def get(self, request, trace_id):
        """根据 trace_id 获取完整调用链日志。

        参数:
            request: Django REST Framework 的 Request 对象。
            trace_id: URL 路径参数，链路追踪唯一标识。
        返回:
            JSON 响应，包含 trace_id、status、时间范围及 logs 列表。若 trace 不存在返回 404。
        """
        _, permission_error = _require_manage_permission(request)
        if permission_error is not None:
            return permission_error
        result = get_trace(trace_id)
        if result is None:
            return error_response(code=404, message="Trace not found.", status_code=404)
        return success_response(data=result)


class GatewayErrorsView(APIView):
    """网关错误视图。

    GET /api/llm/gateway/errors/ — 返回指定时间窗口内的聚合错误类型及最近错误样本。
    """
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        """获取错误统计。

        参数:
            request: Django REST Framework 的 Request 对象，支持 time 参数（时间窗口预设）。
        返回:
            JSON 响应，包含 total_failed_requests、error_types（错误码分布）、recent_errors（最近 20 条错误）。
        """
        _, permission_error = _require_manage_permission(request)
        if permission_error is not None:
            return permission_error
        time_preset = request.query_params.get("time") or "24h"
        return success_response(data=get_errors(time_preset=time_preset))


class GatewayCostsSummaryView(APIView):
    """网关成本摘要视图。

    GET /api/llm/gateway/costs/summary/ — 返回指定时间窗口内的 Token 用量和估算成本汇总。
    """
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        """获取成本摘要。

        参数:
            request: Django REST Framework 的 Request 对象，支持 model/status/time 筛选参数。
        返回:
            JSON 响应，包含 total_requests、token 用量和 estimated 成本。
        """
        _, permission_error = _require_manage_permission(request)
        if permission_error is not None:
            return permission_error
        filters = _parse_query_filters(request)
        return success_response(data=get_costs_summary(filters))


class GatewayCostsTimeseriesView(APIView):
    """网关成本时序视图。

    GET /api/llm/gateway/costs/timeseries/ — 返回按时间桶聚合的请求量和成本时序数据。
    """
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        """获取成本时序数据。

        参数:
            request: Django REST Framework 的 Request 对象，支持 model/status/time 筛选参数。
                     time 决定时间桶粒度：1h -> 分钟级，24h -> 小时级，7d -> 6小时级，30d -> 天级。
        返回:
            JSON 响应，包含 granularity_hours/minutes 和 points（时序数据点列表）。
        """
        _, permission_error = _require_manage_permission(request)
        if permission_error is not None:
            return permission_error
        filters = _parse_query_filters(request)
        return success_response(data=get_costs_timeseries(filters))


class GatewayCostsModelsView(APIView):
    """网关按模型成本视图。

    GET /api/llm/gateway/costs/models/ — 返回按模型别名分组的用量和成本明细。
    """
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        """获取按模型分组的成本明细。

        参数:
            request: Django REST Framework 的 Request 对象，支持 model/status/time 筛选参数。
        返回:
            JSON 响应，包含 total_requests 和 models 列表（每个模型的请求量/占比/token/成本）。
        """
        _, permission_error = _require_manage_permission(request)
        if permission_error is not None:
            return permission_error
        filters = _parse_query_filters(request)
        return success_response(data=get_costs_models(filters))
