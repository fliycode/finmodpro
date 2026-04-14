from rest_framework.views import APIView

from common.api_response import error_response, success_response
from llm.controllers.model_config_controller import _require_manage_permission
from llm.serializers import (
    FineTuneRunCreateSerializer,
    FineTuneRunSummarySerializer,
    FineTuneRunUpdateSerializer,
)
from llm.services.fine_tune_service import (
    create_fine_tune_run,
    get_fine_tune_run,
    list_fine_tune_runs,
    update_fine_tune_run,
)


class FineTuneRunListCreateView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        _, permission_error = _require_manage_permission(request)
        if permission_error is not None:
            return permission_error

        base_model_id = request.query_params.get("base_model_id")
        fine_tune_runs = list_fine_tune_runs(base_model_id=base_model_id)
        return success_response(
            data={
                "total": fine_tune_runs.count(),
                "fine_tune_runs": FineTuneRunSummarySerializer(fine_tune_runs, many=True).data,
            }
        )

    def post(self, request):
        _, permission_error = _require_manage_permission(request)
        if permission_error is not None:
            return permission_error

        serializer = FineTuneRunCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            fine_tune_run = create_fine_tune_run(payload=serializer.validated_data)
        except ValueError:
            return error_response(code=404, message="模型配置不存在。", status_code=404)

        return success_response(
            data={"fine_tune_run": FineTuneRunSummarySerializer(fine_tune_run).data},
            status_code=201,
        )


class FineTuneRunDetailView(APIView):
    authentication_classes = []
    permission_classes = []

    def patch(self, request, fine_tune_run_id):
        _, permission_error = _require_manage_permission(request)
        if permission_error is not None:
            return permission_error

        fine_tune_run = get_fine_tune_run(fine_tune_run_id=fine_tune_run_id)
        if fine_tune_run is None:
            return error_response(code=404, message="微调记录不存在。", status_code=404)

        serializer = FineTuneRunUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        updated = update_fine_tune_run(fine_tune_run=fine_tune_run, payload=serializer.validated_data)
        return success_response(data={"fine_tune_run": FineTuneRunSummarySerializer(updated).data})
