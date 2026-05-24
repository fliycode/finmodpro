"""
微调导出服务（类比 SpringBoot 中 @Service 的训练数据导出层）。

负责：
- 创建微调导出包（训练样本、manifest 清单、dataset_info 配置、README）
- 读取已有导出包的详情（清单和文件列表）
- 构建 Runner 所需的执行规格 payload（包含导出文件、训练配置、回调契约）

类比 SpringBoot 中负责将训练数据导出为特定格式（如 LLaMA-Factory 的 ShareGPT 格式）
并打包为可分发制品的工作流 Service。
"""
import json
from pathlib import Path

from django.conf import settings


def _build_placeholder_samples(*, fine_tune_run):
    """构建占位训练样本（当前阶段尚未接入真实监督数据）。

    在真实数据集构建器接入之前，为每个微调运行生成一条占位对话样本，
    确保 LLaMA-Factory 能加载到有效格式的数据文件。

    参数:
        fine_tune_run: FineTuneRun 实例，包含 dataset_name 和 base_model 信息。

    返回:
        list[dict]，包含单条 messages 格式的对话样本（user/assistant 角色）。
    """
    dataset_label = fine_tune_run.dataset_name or "未命名训练集"
    prompt = (
        f"你是 FinModPro 的训练样本导出占位数据。"
        f" 数据集：{dataset_label}。"
        f" 基础模型：{fine_tune_run.base_model.model_name}。"
    )
    response = fine_tune_run.notes or "当前阶段尚未接入真实监督数据导出，这是一条占位样本。"
    return [{"messages": [{"role": "user", "content": prompt}, {"role": "assistant", "content": response}]}]


def _write_json(path, payload):
    """将 Python 对象写入 JSON 文件（UTF-8 编码，indent=2 格式化）。

    参数:
        path: Path 对象，目标文件路径。
        payload: 可 JSON 序列化的 Python 对象。
    """
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def create_export_bundle(*, fine_tune_run):
    """为微调运行创建完整的导出数据包。

    生成物包括：
    - manifest.json: 数据集清单（基础模型、任务类型、样本数等元信息）
    - dataset_info.json: LLaMA-Factory 格式的 dataset_info 配置
    - train.jsonl: ShareGPT 格式的训练样本（当前为占位数据）
    - README.md: 导出说明

    类比 SpringBoot 中一个生成多文件制品的 Builder 或 Factory 方法。

    参数:
        fine_tune_run: FineTuneRun 实例，导出基础（run_key 用作目录名）。

    返回:
        dict，包含：
        - export_path: str，导出目录的绝对路径
        - dataset_manifest: dict，数据集清单元信息
    """
    export_root = Path(settings.FINE_TUNE_EXPORT_ROOT)
    export_dir = export_root / fine_tune_run.run_key
    export_dir.mkdir(parents=True, exist_ok=True)

    train_samples = _build_placeholder_samples(fine_tune_run=fine_tune_run)
    manifest = {
        "fine_tune_run_id": fine_tune_run.id,
        "run_key": fine_tune_run.run_key,
        "base_model_id": fine_tune_run.base_model_id,
        "base_model_name": fine_tune_run.base_model.name,
        "base_model_provider": fine_tune_run.base_model.provider,
        "dataset_name": fine_tune_run.dataset_name,
        "dataset_version": fine_tune_run.dataset_version,
        "task_type": "chat",
        "sample_count": len(train_samples),
        "format": "llamafactory-conversations",
        "created_by": "finmodpro",
        "export_status": "ready",
        "placeholder": True,
        "source_snapshot": {
            "strategy": fine_tune_run.strategy,
            "notes": fine_tune_run.notes,
        },
    }
    dataset_info = {
        "finmodpro_train": {
            "file_name": "train.jsonl",
            "formatting": "sharegpt",
            "columns": {"messages": "messages"},
            "tags": {"role_tag": "role", "content_tag": "content", "user_tag": "user", "assistant_tag": "assistant"},
        }
    }

    _write_json(export_dir / "manifest.json", manifest)
    _write_json(export_dir / "dataset_info.json", dataset_info)
    (export_dir / "train.jsonl").write_text(
        "\n".join(json.dumps(item, ensure_ascii=False) for item in train_samples) + "\n",
        encoding="utf-8",
    )
    (export_dir / "README.md").write_text(
        "# FinModPro fine-tune export\n\n"
        "This phase-one export is intentionally placeholder-backed until a real supervised dataset "
        "builder is wired into the control plane.\n",
        encoding="utf-8",
    )

    return {
        "export_path": str(export_dir),
        "dataset_manifest": manifest,
    }


def get_export_bundle_detail(*, fine_tune_run):
    """读取微调导出包的详细信息。

    若导出目录不存在则返回空文件列表和空 manifest。

    参数:
        fine_tune_run: FineTuneRun 实例（需包含 export_path）。

    返回:
        dict，包含：
        - fine_tune_run_id: 微调运行 ID
        - run_key: 运行标识
        - export_path: 导出路径
        - manifest: dict，manifest.json 内容（不存在则为空字典）
        - files: list[dict]，导出目录下的文件列表（name、path、size_bytes）
    """
    export_dir = Path(fine_tune_run.export_path or "")
    if not export_dir.exists():
        return {
            "fine_tune_run_id": fine_tune_run.id,
            "run_key": fine_tune_run.run_key,
            "export_path": fine_tune_run.export_path,
            "manifest": {},
            "files": [],
        }

    manifest_path = export_dir / "manifest.json"
    manifest = {}
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    files = []
    for path in sorted(export_dir.iterdir()):
        files.append(
            {
                "name": path.name,
                "path": str(path),
                "size_bytes": path.stat().st_size if path.is_file() else 0,
            }
        )

    return {
        "fine_tune_run_id": fine_tune_run.id,
        "run_key": fine_tune_run.run_key,
        "export_path": str(export_dir),
        "manifest": manifest,
        "files": files,
    }


def get_runner_execution_spec(*, fine_tune_run, request, include_callback_token=False):
    """构建 Runner 所需的完整执行规格 payload。

    聚合以下信息：
    - 导出包（文件列表及下载 URL）
    - 训练任务配置（框架、策略、基础模型等）
    - 回调契约（回调 URL 和认证 token）
    - Runner 目标服务器信息
    - 平台 API base URL

    类比 SpringBoot 中构建一个发给远程服务的完整 DTO（Data Transfer Object）。

    参数:
        fine_tune_run: FineTuneRun 实例。
        request: HttpRequest 实例，用于 build_absolute_uri 构建完整的回调 URL。
        include_callback_token: bool，是否在 payload 中包含明文回调令牌（派发时需要，查询时不需要）。

    返回:
        dict，Runner 执行规格，包含 platform、runner_target、training_job、
        export_bundle、callback 五大块信息。
    """
    export_detail = get_export_bundle_detail(fine_tune_run=fine_tune_run)
    base_url = settings.FINE_TUNE_EXPORT_BASE_URL.strip().rstrip("/")

    export_files = []
    for item in export_detail["files"]:
        file_url = ""
        if base_url:
            file_url = f"{base_url}/{fine_tune_run.run_key}/{item['name']}"
        export_files.append(
            {
                **item,
                "url": file_url,
            }
        )

    callback_contract = {
        "url": request.build_absolute_uri(f"/api/ops/fine-tunes/{fine_tune_run.id}/callback/"),
        "token_header": "X-Fine-Tune-Token",
    }
    if include_callback_token:
        callback_contract["token"] = fine_tune_run.callback_token_value

    runner_target = {
        "server_id": fine_tune_run.runner_server_id,
        "name": "",
        "base_url": "",
        "default_work_dir": "",
    }
    if fine_tune_run.runner_server_id:
        runner_target = {
            "server_id": fine_tune_run.runner_server_id,
            "name": fine_tune_run.runner_server.name,
            "base_url": fine_tune_run.runner_server.base_url,
            "default_work_dir": fine_tune_run.runner_server.default_work_dir,
        }

    return {
        "fine_tune_run_id": fine_tune_run.id,
        "run_key": fine_tune_run.run_key,
        "status": fine_tune_run.status,
        "platform": {
            "api_base_url": request.build_absolute_uri("/").rstrip("/"),
        },
        "runner_target": runner_target,
        "training_job": {
            "framework": "llamafactory",
            "strategy": fine_tune_run.strategy,
            "base_model_name": fine_tune_run.base_model.model_name,
            "runner_name": fine_tune_run.runner_name,
            "training_config": fine_tune_run.training_config,
            "dataset_name": fine_tune_run.dataset_name,
            "dataset_version": fine_tune_run.dataset_version,
        },
        "export_bundle": {
            "export_path": export_detail["export_path"],
            "base_url": base_url,
            "manifest": export_detail["manifest"],
            "files": export_files,
        },
        "callback": callback_contract,
    }
