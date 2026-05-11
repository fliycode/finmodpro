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
from systemcheck.models import AuditRecord
from systemcheck.services.audit_service import record_audit_event


def _build_runner_server_audit_payload(runner_server):
    return {
        "name": runner_server.name,
        "base_url": runner_server.base_url,
        "default_work_dir": runner_server.default_work_dir,
        "is_enabled": bool(runner_server.is_enabled),
        "has_auth_token": bool(runner_server.auth_token),
    }


def _build_fine_tune_run_audit_payload(fine_tune_run):
    return {
        "base_model_name": fine_tune_run.base_model.name,
        "dataset_name": fine_tune_run.dataset_name,
        "dataset_version": fine_tune_run.dataset_version,
        "strategy": fine_tune_run.strategy,
        "status": fine_tune_run.status,
        "runner_server_name": fine_tune_run.runner_server.name if fine_tune_run.runner_server_id else "",
        "runner_name": fine_tune_run.runner_name,
    }


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
        user, permission_error = _require_manage_permission(request)
        if permission_error is not None:
            return permission_error

        serializer = FineTuneRunnerServerWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        runner_server = create_fine_tune_runner_server(payload=serializer.validated_data)
        record_audit_event(
            actor=user,
            action="llm.fine_tune_runner_server.create",
            target_type="fine_tune_runner_server",
            target_id=runner_server.id,
            status=AuditRecord.STATUS_SUCCEEDED,
            detail_payload=_build_runner_server_audit_payload(runner_server),
        )
        return success_response(
            data={"fine_tune_server": FineTuneRunnerServerSummarySerializer(runner_server).data},
            status_code=201,
        )


class FineTuneRunnerServerDetailView(APIView):
    authentication_classes = []
    permission_classes = []

    def patch(self, request, runner_server_id):
        user, permission_error = _require_manage_permission(request)
        if permission_error is not None:
            return permission_error

        runner_server = get_fine_tune_runner_server(runner_server_id=runner_server_id)
        if runner_server is None:
            record_audit_event(
                actor=user,
                action="llm.fine_tune_runner_server.update",
                target_type="fine_tune_runner_server",
                target_id=runner_server_id,
                status=AuditRecord.STATUS_FAILED,
                detail_payload={"error": "训练服务器不存在。"},
            )
            return error_response(code=404, message="训练服务器不存在。", status_code=404)

        serializer = FineTuneRunnerServerWriteSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        updated = update_fine_tune_runner_server(
            runner_server=runner_server,
            payload=serializer.validated_data,
        )
        record_audit_event(
            actor=user,
            action="llm.fine_tune_runner_server.update",
            target_type="fine_tune_runner_server",
            target_id=updated.id,
            status=AuditRecord.STATUS_SUCCEEDED,
            detail_payload=_build_runner_server_audit_payload(updated),
        )
        return success_response(data={"fine_tune_server": FineTuneRunnerServerSummarySerializer(updated).data})

    def delete(self, request, runner_server_id):
        user, permission_error = _require_manage_permission(request)
        if permission_error is not None:
            return permission_error

        runner_server = get_fine_tune_runner_server(runner_server_id=runner_server_id)
        if runner_server is None:
            record_audit_event(
                actor=user,
                action="llm.fine_tune_runner_server.delete",
                target_type="fine_tune_runner_server",
                target_id=runner_server_id,
                status=AuditRecord.STATUS_FAILED,
                detail_payload={"error": "训练服务器不存在。"},
            )
            return error_response(code=404, message="训练服务器不存在。", status_code=404)

        runner_server_payload = _build_runner_server_audit_payload(runner_server)
        delete_fine_tune_runner_server(runner_server=runner_server)
        record_audit_event(
            actor=user,
            action="llm.fine_tune_runner_server.delete",
            target_type="fine_tune_runner_server",
            target_id=runner_server_id,
            status=AuditRecord.STATUS_SUCCEEDED,
            detail_payload=runner_server_payload,
        )
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
        user, permission_error = _require_manage_permission(request)
        if permission_error is not None:
            return permission_error

        serializer = FineTuneRunCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            fine_tune_run = create_fine_tune_run(payload=serializer.validated_data)
        except ValueError as exc:
            record_audit_event(
                actor=user,
                action="llm.fine_tune_run.create",
                target_type="fine_tune_run",
                target_id="",
                status=AuditRecord.STATUS_FAILED,
                detail_payload={
                    "dataset_name": serializer.validated_data.get("dataset_name", ""),
                    "dataset_version": serializer.validated_data.get("dataset_version", ""),
                    "strategy": serializer.validated_data.get("strategy", ""),
                    "base_model_id": serializer.validated_data.get("base_model_id", ""),
                    "runner_server_id": serializer.validated_data.get("runner_server_id", ""),
                    "error": str(exc),
                },
            )
            return error_response(code=404, message=str(exc), status_code=404)

        record_audit_event(
            actor=user,
            action="llm.fine_tune_run.create",
            target_type="fine_tune_run",
            target_id=fine_tune_run.id,
            status=AuditRecord.STATUS_SUCCEEDED,
            detail_payload=_build_fine_tune_run_audit_payload(fine_tune_run),
        )
        return success_response(
            data={"fine_tune_run": FineTuneRunSummarySerializer(fine_tune_run).data},
            status_code=201,
        )


class FineTuneRunDetailView(APIView):
    authentication_classes = []
    permission_classes = []

    def patch(self, request, fine_tune_run_id):
        user, permission_error = _require_manage_permission(request)
        if permission_error is not None:
            return permission_error

        fine_tune_run = get_fine_tune_run(fine_tune_run_id=fine_tune_run_id)
        if fine_tune_run is None:
            record_audit_event(
                actor=user,
                action="llm.fine_tune_run.update",
                target_type="fine_tune_run",
                target_id=fine_tune_run_id,
                status=AuditRecord.STATUS_FAILED,
                detail_payload={"error": "微调记录不存在。"},
            )
            return error_response(code=404, message="微调记录不存在。", status_code=404)

        serializer = FineTuneRunUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        try:
            updated = update_fine_tune_run(fine_tune_run=fine_tune_run, payload=serializer.validated_data)
        except ValueError as exc:
            record_audit_event(
                actor=user,
                action="llm.fine_tune_run.update",
                target_type="fine_tune_run",
                target_id=fine_tune_run.id,
                status=AuditRecord.STATUS_FAILED,
                detail_payload={**_build_fine_tune_run_audit_payload(fine_tune_run), "error": str(exc)},
            )
            return error_response(code=404, message=str(exc), status_code=404)
        record_audit_event(
            actor=user,
            action="llm.fine_tune_run.update",
            target_type="fine_tune_run",
            target_id=updated.id,
            status=AuditRecord.STATUS_SUCCEEDED,
            detail_payload=_build_fine_tune_run_audit_payload(updated),
        )
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
        user, permission_error = _require_manage_permission(request)
        if permission_error is not None:
            return permission_error

        fine_tune_run = get_fine_tune_run(fine_tune_run_id=fine_tune_run_id)
        if fine_tune_run is None:
            record_audit_event(
                actor=user,
                action="llm.fine_tune_run.dispatch",
                target_type="fine_tune_run",
                target_id=fine_tune_run_id,
                status=AuditRecord.STATUS_FAILED,
                detail_payload={"error": "微调记录不存在。"},
            )
            return error_response(code=404, message="微调记录不存在。", status_code=404)

        try:
            result = submit_fine_tune_run(fine_tune_run=fine_tune_run, request_context=request)
        except ValueError as exc:
            record_audit_event(
                actor=user,
                action="llm.fine_tune_run.dispatch",
                target_type="fine_tune_run",
                target_id=fine_tune_run.id,
                status=AuditRecord.STATUS_FAILED,
                detail_payload={**_build_fine_tune_run_audit_payload(fine_tune_run), "error": str(exc)},
            )
            return error_response(code=400, message=str(exc), status_code=400)
        except RuntimeError as exc:
            record_audit_event(
                actor=user,
                action="llm.fine_tune_run.dispatch",
                target_type="fine_tune_run",
                target_id=fine_tune_run.id,
                status=AuditRecord.STATUS_FAILED,
                detail_payload={**_build_fine_tune_run_audit_payload(fine_tune_run), "error": str(exc)},
            )
            return error_response(code=502, message=str(exc), status_code=502)

        record_audit_event(
            actor=user,
            action="llm.fine_tune_run.dispatch",
            target_type="fine_tune_run",
            target_id=result["fine_tune_run"].id,
            status=AuditRecord.STATUS_SUBMITTED,
            detail_payload={
                **_build_fine_tune_run_audit_payload(result["fine_tune_run"]),
                "job_id": result["dispatch"]["job_id"],
                "dispatch_status": result["dispatch"]["status"],
            },
        )
        return success_response(
            data={
                "dispatch": result["dispatch"],
                "fine_tune_run": FineTuneRunSummarySerializer(result["fine_tune_run"]).data,
            }
        )
