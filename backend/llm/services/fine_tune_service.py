"""
微调管理服务（类比 SpringBoot 中 @Service 的业务逻辑层）。
提供微调训练服务器和运行记录的完整 CRUD 操作。
创建运行记录时会自动生成本地导出包（export bundle）。
"""
import secrets

from django.utils import timezone

from llm.models import FineTuneRun, FineTuneRunnerServer, ModelConfig
from llm.services.fine_tune_callback_service import hash_callback_token
from llm.services.fine_tune_export_service import create_export_bundle


# ===================== 训练服务器 服务 =====================

def list_fine_tune_runner_servers():
    """列出所有微调训练服务器。

    返回:
        QuerySet，按名称和 ID 排序。
    """
    return FineTuneRunnerServer.objects.order_by("name", "id")


def get_fine_tune_runner_server(*, runner_server_id):
    """按 ID 获取训练服务器。

    参数:
        runner_server_id: int，训练服务器主键 ID。
    返回:
        FineTuneRunnerServer 实例或 None。
    """
    return FineTuneRunnerServer.objects.filter(id=runner_server_id).first()


def create_fine_tune_runner_server(*, payload):
    """创建新的训练服务器。

    参数:
        payload: dict，包含 name、base_url、auth_token 等字段。
    返回:
        FineTuneRunnerServer 实例，新创建的服务器。
    """
    return FineTuneRunnerServer.objects.create(**payload)


def update_fine_tune_runner_server(*, runner_server, payload):
    """更新训练服务器配置。

    特别处理 auth_token：若传入空值则跳过（不清除已有的 token）。

    参数:
        runner_server: FineTuneRunnerServer 实例，待更新。
        payload: dict，包含要更新的字段。
    返回:
        FineTuneRunnerServer 实例，更新后的服务器。
    """
    auth_token = payload.pop("auth_token", None)
    for key, value in payload.items():
        setattr(runner_server, key, value)
    if auth_token not in {None, ""}:
        runner_server.auth_token = auth_token
    runner_server.save()
    runner_server.refresh_from_db()
    return runner_server


def delete_fine_tune_runner_server(*, runner_server):
    """删除训练服务器。

    参数:
        runner_server: FineTuneRunnerServer 实例，待删除。
    """
    runner_server.delete()


# ===================== 微调运行 服务 =====================

def list_fine_tune_runs(*, base_model_id=None):
    """列出微调运行记录。

    参数:
        base_model_id: int 或 None，按基础模型 ID 筛选（可选）。
    返回:
        QuerySet，预加载 base_model、registered_model_config、runner_server 外键。
    """
    queryset = FineTuneRun.objects.select_related(
        "base_model",
        "registered_model_config",
        "runner_server",
    ).order_by("-created_at", "-id")
    if base_model_id:
        queryset = queryset.filter(base_model_id=base_model_id)
    return queryset


def get_fine_tune_run(*, fine_tune_run_id):
    """按 ID 获取微调运行记录。

    参数:
        fine_tune_run_id: int，运行记录主键 ID。
    返回:
        FineTuneRun 实例或 None。
    """
    return FineTuneRun.objects.select_related(
        "base_model",
        "registered_model_config",
        "runner_server",
    ).filter(id=fine_tune_run_id).first()


def create_fine_tune_run(*, payload):
    """创建新的微调运行记录。

    内部流程：
    1. 验证基础模型和训练服务器存在
    2. 生成唯一的 run_key 和回调令牌
    3. 创建 FineTuneRun 记录
    4. 调用 create_export_bundle 生成导出包
    5. 将临时属性 callback_token 挂载到实例上供序列化器使用

    参数:
        payload: dict，包含 base_model_id、dataset_name、strategy 等字段。
    返回:
        FineTuneRun 实例（附有临时属性 callback_token）。
    异常:
        ValueError: 当基础模型或训练服务器不存在时抛出。
    """
    base_model_id = payload.pop("base_model_id")
    base_model = ModelConfig.objects.filter(id=base_model_id).first()
    if base_model is None:
        raise ValueError("模型配置不存在。")
    runner_server_id = payload.pop("runner_server_id", None)
    runner_server = None
    if runner_server_id is not None:
        runner_server = FineTuneRunnerServer.objects.filter(id=runner_server_id).first()
        if runner_server is None:
            raise ValueError("训练服务器不存在。")

    now = timezone.now()
    run_key = f"ft-{now.strftime('%Y%m%d%H%M%S')}-{secrets.token_hex(3)}"
    callback_token = f"ftcb_{secrets.token_urlsafe(24)}"
    fine_tune_run = FineTuneRun.objects.create(
        base_model=base_model,
        runner_server=runner_server,
        run_key=run_key,
        queued_at=now,
        callback_token_hash=hash_callback_token(callback_token),
        callback_token_value=callback_token,
        dataset_manifest={"dataset_name": payload.get("dataset_name", ""), "export_status": "pending"},
        training_config=payload.pop("training_config", {}),
        runner_name=payload.pop("runner_name", ""),
        **payload,
    )
    export_result = create_export_bundle(fine_tune_run=fine_tune_run)
    fine_tune_run.export_path = export_result["export_path"]
    fine_tune_run.dataset_manifest = export_result["dataset_manifest"]
    fine_tune_run.save(update_fields=["export_path", "dataset_manifest", "updated_at"])
    fine_tune_run.refresh_from_db()
    fine_tune_run.callback_token = callback_token  # 临时属性，仅供本次请求返回
    return fine_tune_run


def update_fine_tune_run(*, fine_tune_run, payload):
    """更新微调运行记录。

    特殊处理：
    - runner_server_id: 可重新绑定训练服务器（设为 None 则解绑）
    - metrics / artifact_manifest: 仅当传入新值时才更新（不传则保留原值）

    参数:
        fine_tune_run: FineTuneRun 实例，待更新。
        payload: dict，包含要更新的字段。
    返回:
        FineTuneRun 实例，更新后的记录。
    异常:
        ValueError: 当指定的 runner_server_id 对应服务器不存在时抛出。
    """
    incoming_metrics = payload.pop("metrics", None)
    incoming_artifact_manifest = payload.pop("artifact_manifest", None)
    if "runner_server_id" in payload:
        runner_server_id = payload.pop("runner_server_id")
        if runner_server_id is None:
            fine_tune_run.runner_server = None
        else:
            runner_server = FineTuneRunnerServer.objects.filter(id=runner_server_id).first()
            if runner_server is None:
                raise ValueError("训练服务器不存在。")
            fine_tune_run.runner_server = runner_server
    for key, value in payload.items():
        setattr(fine_tune_run, key, value)
    if incoming_metrics is not None:
        fine_tune_run.metrics = incoming_metrics
    if incoming_artifact_manifest is not None:
        fine_tune_run.artifact_manifest = incoming_artifact_manifest
    fine_tune_run.save()
    fine_tune_run.refresh_from_db()
    return fine_tune_run
