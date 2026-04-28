from rest_framework.views import APIView

from common.api_response import error_response, success_response
from llm.controllers.model_config_controller import _require_manage_permission
from llm.serializers import (
    FineTuneRunCallbackSerializer,
    FineTuneRunCreateSerializer,
    FineTuneRunnerServerSummarySerializer,
    FineTuneRunnerServerWriteSerializer,
    FineTuneRunSummarySerializer,
    FineTuneRunUpdateSerializer,
)
from llm.services.fine_tune_callback_service import apply_runner_callback, verify_callback_token
from llm.services.fine_tune_dispatch_service import submit_fine_tune_run
from llm.services.fine_tune_export_service import get_export_bundle_detail, get_runner_execution_spec
from llm.services.fine_tune_service import (
    create_fine_tune_run,
    create_fine_tune_runner_server,
    delete_fine_tune_runner_server,
    get_fine_tune_runner_server,
    get_fine_tune_run,
    list_fine_tune_runner_servers,
    list_fine_tune_runs,
    update_fine_tune_runner_server,
    update_fine_tune_run,
)


class FineTuneRunnerServerListCreateView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        _, permission_error = _require_manage_permission(request)
        if permission_error is not None:
            return permission_error

        runner_servers = list_fine_tune_runner_servers()
        return success_response(
            data={
                "total": runner_servers.count(),
                "fine_tune_servers": FineTuneRunnerServerSummarySerializer(runner_servers, many=True).data,
            }
        )

    def post(self, request):
        _, permission_error = _require_manage_permission(request)
        if permission_error is not None:
            return permission_error

        serializer = FineTuneRunnerServerWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        runner_server = create_fine_tune_runner_server(payload=serializer.validated_data)
        return success_response(
            data={"fine_tune_server": FineTuneRunnerServerSummarySerializer(runner_server).data},
            status_code=201,
        )


class FineTuneRunnerServerDetailView(APIView):
    authentication_classes = []
    permission_classes = []

    def patch(self, request, runner_server_id):
        _, permission_error = _require_manage_permission(request)
        if permission_error is not None:
            return permission_error

        runner_server = get_fine_tune_runner_server(runner_server_id=runner_server_id)
        if runner_server is None:
            return error_response(code=404, message="训练服务器不存在。", status_code=404)

        serializer = FineTuneRunnerServerWriteSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        updated = update_fine_tune_runner_server(
            runner_server=runner_server,
            payload=serializer.validated_data,
        )
        return success_response(data={"fine_tune_server": FineTuneRunnerServerSummarySerializer(updated).data})

    def delete(self, request, runner_server_id):
        _, permission_error = _require_manage_permission(request)
        if permission_error is not None:
            return permission_error

        runner_server = get_fine_tune_runner_server(runner_server_id=runner_server_id)
        if runner_server is None:
            return error_response(code=404, message="训练服务器不存在。", status_code=404)

        delete_fine_tune_runner_server(runner_server=runner_server)
        return success_response(data={"deleted": True})


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
        except ValueError as exc:
            return error_response(code=404, message=str(exc), status_code=404)

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
        try:
            updated = update_fine_tune_run(fine_tune_run=fine_tune_run, payload=serializer.validated_data)
        except ValueError as exc:
            return error_response(code=404, message=str(exc), status_code=404)
        return success_response(data={"fine_tune_run": FineTuneRunSummarySerializer(updated).data})


class FineTuneRunCallbackView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request, fine_tune_run_id):
        fine_tune_run = get_fine_tune_run(fine_tune_run_id=fine_tune_run_id)
        if fine_tune_run is None:
            return error_response(code=404, message="微调记录不存在。", status_code=404)

        callback_token = request.headers.get("X-Fine-Tune-Token", "")
        if not verify_callback_token(fine_tune_run=fine_tune_run, token=callback_token):
            return error_response(code=401, message="回调令牌无效。", status_code=401)

        serializer = FineTuneRunCallbackSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        updated = apply_runner_callback(fine_tune_run=fine_tune_run, payload=serializer.validated_data)
        return success_response(data={"fine_tune_run": FineTuneRunSummarySerializer(updated).data})


class FineTuneRunExportDetailView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request, fine_tune_run_id):
        _, permission_error = _require_manage_permission(request)
        if permission_error is not None:
            return permission_error

        fine_tune_run = get_fine_tune_run(fine_tune_run_id=fine_tune_run_id)
        if fine_tune_run is None:
            return error_response(code=404, message="微调记录不存在。", status_code=404)

        return success_response(data=get_export_bundle_detail(fine_tune_run=fine_tune_run))


class FineTuneRunRunnerSpecView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request, fine_tune_run_id):
        fine_tune_run = get_fine_tune_run(fine_tune_run_id=fine_tune_run_id)
        if fine_tune_run is None:
            return error_response(code=404, message="微调记录不存在。", status_code=404)

        callback_token = request.headers.get("X-Fine-Tune-Token", "")
        if not verify_callback_token(fine_tune_run=fine_tune_run, token=callback_token):
            return error_response(code=401, message="回调令牌无效。", status_code=401)

        return success_response(data=get_runner_execution_spec(fine_tune_run=fine_tune_run, request=request))


class FineTuneRunDispatchView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request, fine_tune_run_id):
        _, permission_error = _require_manage_permission(request)
        if permission_error is not None:
            return permission_error

        fine_tune_run = get_fine_tune_run(fine_tune_run_id=fine_tune_run_id)
        if fine_tune_run is None:
            return error_response(code=404, message="微调记录不存在。", status_code=404)

        try:
            result = submit_fine_tune_run(fine_tune_run=fine_tune_run, request_context=request)
        except ValueError as exc:
            return error_response(code=400, message=str(exc), status_code=400)
        except RuntimeError as exc:
            return error_response(code=502, message=str(exc), status_code=502)

        return success_response(
            data={
                "dispatch": result["dispatch"],
                "fine_tune_run": FineTuneRunSummarySerializer(result["fine_tune_run"]).data,
            }
        )
