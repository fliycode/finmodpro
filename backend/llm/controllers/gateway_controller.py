from rest_framework.views import APIView

from common.api_response import error_response, success_response
from llm.controllers.model_config_controller import _require_manage_permission
from llm.services.litellm_gateway_query_service import (
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
    return {
        "model": request.query_params.get("model") or None,
        "status": request.query_params.get("status") or None,
        "time": request.query_params.get("time") or "24h",
    }


class GatewaySummaryView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        _, err = _require_manage_permission(request)
        if err:
            return err
        return success_response(data=get_gateway_summary())


class GatewayLogsView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        _, err = _require_manage_permission(request)
        if err:
            return err
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
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        _, err = _require_manage_permission(request)
        if err:
            return err
        filters = _parse_query_filters(request)
        return success_response(data=get_logs_summary(filters))


class GatewayTraceView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request, trace_id):
        _, err = _require_manage_permission(request)
        if err:
            return err
        result = get_trace(trace_id)
        if result is None:
            return error_response(code=404, message="Trace not found.", status_code=404)
        return success_response(data=result)


class GatewayErrorsView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        _, err = _require_manage_permission(request)
        if err:
            return err
        time_preset = request.query_params.get("time") or "24h"
        return success_response(data=get_errors(time_preset=time_preset))


class GatewayCostsSummaryView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        _, err = _require_manage_permission(request)
        if err:
            return err
        filters = _parse_query_filters(request)
        return success_response(data=get_costs_summary(filters))


class GatewayCostsTimeseriesView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        _, err = _require_manage_permission(request)
        if err:
            return err
        filters = _parse_query_filters(request)
        return success_response(data=get_costs_timeseries(filters))


class GatewayCostsModelsView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        _, err = _require_manage_permission(request)
        if err:
            return err
        filters = _parse_query_filters(request)
        return success_response(data=get_costs_models(filters))
