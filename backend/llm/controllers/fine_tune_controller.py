"""
微调管理控制器（类比 SpringBoot 中 @RestController）。
提供微调训练服务器和运行记录的完整生命周期管理：
- FineTuneRunnerServer: 训练服务器的 CRUD
- FineTuneRun: 训练任务的创建、更新、派发、回调处理、导出
所有写操作均需要 auth.manage_model_config 权限，并记录审计日志。
"""
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
    """构建微调训练服务器的审计日志负载。

    参数:
        runner_server: FineTuneRunnerServer 实例。
    返回:
        dict，包含服务器名称、URL、工作目录、启用状态等。
    """
    return {
        "name": runner_server.name,
        "base_url": runner_server.base_url,
        "default_work_dir": runner_server.default_work_dir,
        "is_enabled": bool(runner_server.is_enabled),
        "has_auth_token": bool(runner_server.auth_token),
    }


def _build_fine_tune_run_audit_payload(fine_tune_run):
    """构建微调运行记录的审计日志负载。

    参数:
        fine_tune_run: FineTuneRun 实例。
    返回:
        dict，包含基础模型名、数据集、策略、状态、服务器信息等。
    """
    return {
        "base_model_name": fine_tune_run.base_model.name,
        "dataset_name": fine_tune_run.dataset_name,
        "dataset_version": fine_tune_run.dataset_version,
        "strategy": fine_tune_run.strategy,
        "status": fine_tune_run.status,
        "runner_server_name": fine_tune_run.runner_server.name if fine_tune_run.runner_server_id else "",
        "runner_name": fine_tune_run.runner_name,
    }


# ===================== 微调训练服务器 视图 =====================

class FineTuneRunnerServerListCreateView(APIView):
    """微调训练服务器列表与创建视图。

    GET  /api/fine-tune-servers/ — 列出所有训练服务器。
    POST /api/fine-tune-servers/ — 创建新的训练服务器。
    需要 auth.manage_model_config 权限。
    """
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        """列出所有微调训练服务器。

        参数:
            request: Django REST Framework 的 Request 对象。
        返回:
            JSON 响应，包含 total 和 fine_tune_servers 列表。
        """
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
        """创建新的微调训练服务器。

        参数:
            request: Django REST Framework 的 Request 对象，body 包含 name、base_url、auth_token 等。
        返回:
            201 Created JSON 响应，包含新创建的 fine_tune_server 对象。
        """
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
    """微调训练服务器详情视图。

    PATCH  /api/fine-tune-servers/<id>/ — 更新训练服务器配置。
    DELETE /api/fine-tune-servers/<id>/ — 删除训练服务器。
    需要 auth.manage_model_config 权限。
    """
    authentication_classes = []
    permission_classes = []

    def patch(self, request, runner_server_id):
        """更新指定训练服务器。

        参数:
            request: Django REST Framework 的 Request 对象。
            runner_server_id: URL 路径参数，训练服务器主键 ID。
        返回:
            JSON 响应，包含更新后的 fine_tune_server 对象。若不存在返回 404。
        """
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
        """删除指定训练服务器。

        参数:
            request: Django REST Framework 的 Request 对象。
            runner_server_id: URL 路径参数，训练服务器主键 ID。
        返回:
            JSON 响应，包含 {"deleted": True}。若不存在返回 404。
        """
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


# ===================== 微调运行记录 视图 =====================

class FineTuneRunListCreateView(APIView):
    """微调运行记录列表与创建视图。

    GET  /api/fine-tunes/ — 列出所有微调运行记录（可按 base_model_id 筛选）。
    POST /api/fine-tunes/ — 创建新的微调运行记录并生成本地导出包。
    需要 auth.manage_model_config 权限。
    """
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        """列出微调运行记录。

        参数:
            request: Django REST Framework 的 Request 对象，可选 query param:
                     base_model_id（按基础模型筛选）。
        返回:
            JSON 响应，包含 total 和 fine_tune_runs 列表。
        """
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
        """创建新的微调运行记录。

        参数:
            request: Django REST Framework 的 Request 对象，body 包含 base_model_id、dataset_name、
                     strategy、training_config 等。
        返回:
            201 Created JSON 响应，包含新创建的 fine_tune_run 对象（含回调令牌）。
            若基础模型不存在返回 404。
        """
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
    """微调运行记录详情视图。

    PATCH /api/fine-tunes/<id>/ — 更新微调运行记录。
    需要 auth.manage_model_config 权限。
    """
    authentication_classes = []
    permission_classes = []

    def patch(self, request, fine_tune_run_id):
        """更新指定微调运行记录。

        参数:
            request: Django REST Framework 的 Request 对象。
            fine_tune_run_id: URL 路径参数，微调运行记录主键 ID。
        返回:
            JSON 响应，包含更新后的 fine_tune_run 对象。若不存在返回 404。
        """
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
    """微调回调视图。

    POST /api/fine-tunes/<id>/callback/ — 由远程训练 Runner 回调，报告训练状态/指标。
    通过 X-Fine-Tune-Token 请求头进行认证，无需管理权限。
    """
    authentication_classes = []
    permission_classes = []

    def post(self, request, fine_tune_run_id):
        """接收训练 Runner 的回调。

        参数:
            request: Django REST Framework 的 Request 对象，headers 需包含 X-Fine-Tune-Token。
            fine_tune_run_id: URL 路径参数，微调运行记录主键 ID。
        返回:
            JSON 响应，包含更新后的 fine_tune_run 对象。
            若记录不存在返回 404，令牌无效返回 401。
        """
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
    """微调导出详情视图。

    GET /api/fine-tunes/<id>/export/ — 返回微调训练数据导出包的详细内容。
    需要 auth.manage_model_config 权限。
    """
    authentication_classes = []
    permission_classes = []

    def get(self, request, fine_tune_run_id):
        """获取微调导出包详情。

        参数:
            request: Django REST Framework 的 Request 对象。
            fine_tune_run_id: URL 路径参数。
        返回:
            JSON 响应，包含 export_path、manifest 和 files 列表。若记录不存在返回 404。
        """
        _, permission_error = _require_manage_permission(request)
        if permission_error is not None:
            return permission_error

        fine_tune_run = get_fine_tune_run(fine_tune_run_id=fine_tune_run_id)
        if fine_tune_run is None:
            return error_response(code=404, message="微调记录不存在。", status_code=404)

        return success_response(data=get_export_bundle_detail(fine_tune_run=fine_tune_run))


class FineTuneRunRunnerSpecView(APIView):
    """微调 Runner 执行规格视图。

    GET /api/fine-tunes/<id>/runner-spec/ — 由训练 Runner 调用，获取完整的执行规格。
    通过 X-Fine-Tune-Token 请求头进行认证。
    """
    authentication_classes = []
    permission_classes = []

    def get(self, request, fine_tune_run_id):
        """获取 Runner 执行所需的所有信息。

        参数:
            request: Django REST Framework 的 Request 对象，headers 需包含 X-Fine-Tune-Token。
            fine_tune_run_id: URL 路径参数。
        返回:
            JSON 响应，包含平台信息、训练配置、导出包、回调契约等完整规格。
        """
        fine_tune_run = get_fine_tune_run(fine_tune_run_id=fine_tune_run_id)
        if fine_tune_run is None:
            return error_response(code=404, message="微调记录不存在。", status_code=404)

        callback_token = request.headers.get("X-Fine-Tune-Token", "")
        if not verify_callback_token(fine_tune_run=fine_tune_run, token=callback_token):
            return error_response(code=401, message="回调令牌无效。", status_code=401)

        return success_response(data=get_runner_execution_spec(fine_tune_run=fine_tune_run, request=request))


class FineTuneRunDispatchView(APIView):
    """微调任务派发视图。

    POST /api/fine-tunes/<id>/dispatch/ — 将待运行的微调任务派发到远程训练服务器。
    需要 auth.manage_model_config 权限。
    """
    authentication_classes = []
    permission_classes = []

    def post(self, request, fine_tune_run_id):
        """向远程训练服务器派发微调任务。

        参数:
            request: Django REST Framework 的 Request 对象。
            fine_tune_run_id: URL 路径参数。
        返回:
            JSON 响应，包含 dispatch 结果和更新后的 fine_tune_run 对象。
            若记录不存在返回 404，参数错误返回 400，远程调用失败返回 502。
        """
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
