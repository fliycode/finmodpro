"""
微调 Runner 客户端（类比 SpringBoot 中用于与外部 Worker 节点通信的远程调用客户端）。

负责：
- 从 FinModPro 平台拉取 Runner 执行规格（训练任务 + 导出包 + 回调配置）
- 下载并物化导出包到本地工作目录
- 动态构建 LLaMA-Factory CLI 训练命令
- 执行本地微调训练并全程向平台回传状态（running -> succeeded/failed）

类比 SpringBoot 中一个既是 HTTP Client 又是本地 Shell 执行器的工作节点 Agent。
"""
import json
import subprocess
from pathlib import Path
from urllib import request


def _build_api_url(api_base_url, path):
    """拼接 API 基础 URL 与相对路径。

    参数:
        api_base_url: str，平台 API 基础地址（如 http://127.0.0.1:8000）。
        path: str，相对路径（如 /api/ops/fine-tunes/1/runner-spec/）。

    返回:
        str，完整的 API 地址。
    """
    return f"{api_base_url.rstrip('/')}{path}"


def _send_json_request(*, url, method, token, payload=None, timeout=30):
    """向 FinModPro 平台发送带 Token 认证的 JSON HTTP 请求。

    参数:
        url: str，完整的请求 URL。
        method: str，HTTP 方法（GET/POST）。
        token: str，微调回调令牌（放在 X-Fine-Tune-Token 头中）。
        payload: dict 或 None，POST 请求的 JSON body。
        timeout: int，HTTP 超时秒数（默认 30）。

    返回:
        dict，响应中的 data 字段内容。

    异常:
        RuntimeError: 当响应 code 不是 0/200/201 时抛出。
    """
    headers = {
        "Content-Type": "application/json",
        "X-Fine-Tune-Token": token,
    }
    body = None
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
    response = request.urlopen(
        request.Request(url, data=body, headers=headers, method=method),
        timeout=timeout,
    )
    response_payload = json.loads(response.read().decode("utf-8"))
    if response_payload.get("code") not in {0, 200, 201}:
        raise RuntimeError(response_payload.get("message") or "Runner API request failed.")
    return response_payload.get("data") or {}


def fetch_runner_spec(*, api_base_url, fine_tune_run_id, token):
    """从平台拉取 Runner 执行规格。

    调用 GET /api/ops/fine-tunes/{id}/runner-spec/ 获取完整的训练任务定义。

    参数:
        api_base_url: str，平台 API 基础地址。
        fine_tune_run_id: int，微调运行 ID。
        token: str，回调令牌。

    返回:
        dict，Runner 执行规格（包含 training_job、export_bundle、callback 等）。
    """
    return _send_json_request(
        url=_build_api_url(api_base_url, f"/api/ops/fine-tunes/{fine_tune_run_id}/runner-spec/"),
        method="GET",
        token=token,
    )


def report_runner_status(*, api_base_url, fine_tune_run_id, token, payload):
    """向平台回传 Runner 执行状态。

    调用 POST /api/ops/fine-tunes/{id}/callback/ 上报当前状态、产物等信息。

    参数:
        api_base_url: str，平台 API 基础地址。
        fine_tune_run_id: int，微调运行 ID。
        token: str，回调令牌。
        payload: dict，状态信息（status、external_job_id、artifact_manifest 等）。

    返回:
        dict，平台返回的 data 内容。
    """
    return _send_json_request(
        url=_build_api_url(api_base_url, f"/api/ops/fine-tunes/{fine_tune_run_id}/callback/"),
        method="POST",
        token=token,
        payload=payload,
    )


def materialize_export_bundle(*, spec, work_dir):
    """将远程导出包物化到本地工作目录。

    若本地已有缓存则直接返回；否则从平台下载 export_bundle 中的所有文件。

    参数:
        spec: dict，Runner 执行规格（包含 export_bundle.files）。
        work_dir: str，本地工作目录的根路径。

    返回:
        str，物化后的导出包目录路径。

    异常:
        FileNotFoundError: 当导出包无文件或文件缺少 URL 时抛出。
    """
    export_bundle = spec.get("export_bundle") or {}
    export_path = Path(export_bundle.get("export_path") or "")
    if export_path.exists():
        return str(export_path)

    run_key = spec.get("run_key") or "fine-tune-run"
    target_dir = Path(work_dir) / run_key
    target_dir.mkdir(parents=True, exist_ok=True)

    files = export_bundle.get("files") or []
    if not files:
        raise FileNotFoundError("No export bundle files available for runner.")

    for file_item in files:
        file_name = file_item.get("name") or ""
        file_url = file_item.get("url") or ""
        if not file_name or not file_url:
            raise FileNotFoundError(f"Missing downloadable file contract for {file_name or 'unknown file'}.")
        response = request.urlopen(file_url, timeout=30)
        (target_dir / file_name).write_bytes(response.read())

    return str(target_dir)


def build_llamafactory_command(*, spec, export_dir, output_dir):
    """根据训练规格动态构建 LLaMA-Factory CLI 训练命令。

    从 training_config 中提取各项训练参数，映射为 llamafactory-cli train 的命令行参数。
    支持的参数包括：stage、finetuning_type、template、cutoff_len、learning_rate、
    num_train_epochs、lora_rank、lora_alpha 等。

    类比 SpringBoot 中将配置 DTO 转换为命令行参数的 Builder 方法。

    参数:
        spec: dict，Runner 执行规格（包含 training_job）。
        export_dir: str，数据集导出目录路径。
        output_dir: str，模型产物输出目录路径。

    返回:
        list[str]，完整的 LLaMA-Factory CLI 命令参数列表。
    """
    training_job = spec.get("training_job") or {}
    training_config = training_job.get("training_config") or {}
    stage = training_config.get("stage") or "sft"
    finetuning_type = training_config.get("finetuning_type") or training_job.get("strategy") or "lora"

    command = [
        "llamafactory-cli",
        "train",
        "--stage",
        str(stage),
        "--do_train",
        "true",
        "--model_name_or_path",
        training_job.get("base_model_name") or "",
        "--dataset_dir",
        str(export_dir),
        "--dataset",
        "finmodpro_train",
        "--finetuning_type",
        str(finetuning_type),
        "--output_dir",
        str(output_dir),
        "--overwrite_output_dir",
        str(training_config.get("overwrite_output_dir", True)).lower(),
    ]

    def get_config_value(*keys):
        """按优先级从 training_config 中获取配置值。

        参数:
            *keys: 依次尝试的配置键名。
        返回:
            第一个非空非空字符串的值，都不存在则返回 None。
        """
        for key in keys:
            if key in training_config and training_config.get(key) not in {None, ""}:
                return training_config.get(key)
        return None

    def append_option(flag, value):
        """向命令列表追加一个选项及其值。

        参数:
            flag: str，CLI 选项标志（如 "--learning_rate"）。
            value: 选项值，支持 str/int/float/bool/list/tuple。
        """
        if value is None or value == "":
            return
        if isinstance(value, bool):
            command.extend([flag, str(value).lower()])
            return
        if isinstance(value, (list, tuple)):
            command.extend([flag, ",".join(str(item) for item in value)])
            return
        command.extend([flag, str(value)])

    option_mapping = (
        (("template",), "--template"),
        (("cutoff_len",), "--cutoff_len"),
        (("max_samples",), "--max_samples"),
        (("preprocessing_num_workers",), "--preprocessing_num_workers"),
        (("dataloader_num_workers",), "--dataloader_num_workers"),
        (("overwrite_cache",), "--overwrite_cache"),
        (("packing",), "--packing"),
        (("per_device_train_batch_size", "batch_size"), "--per_device_train_batch_size"),
        (("gradient_accumulation_steps",), "--gradient_accumulation_steps"),
        (("learning_rate",), "--learning_rate"),
        (("num_train_epochs", "epochs"), "--num_train_epochs"),
        (("lr_scheduler_type",), "--lr_scheduler_type"),
        (("warmup_ratio",), "--warmup_ratio"),
        (("max_grad_norm",), "--max_grad_norm"),
        (("val_size",), "--val_size"),
        (("per_device_eval_batch_size",), "--per_device_eval_batch_size"),
        (("eval_strategy",), "--eval_strategy"),
        (("eval_steps",), "--eval_steps"),
        (("logging_steps",), "--logging_steps"),
        (("save_steps",), "--save_steps"),
        (("plot_loss",), "--plot_loss"),
        (("save_only_model",), "--save_only_model"),
        (("report_to",), "--report_to"),
        (("bf16",), "--bf16"),
        (("fp16",), "--fp16"),
        (("gradient_checkpointing",), "--gradient_checkpointing"),
        (("lora_rank",), "--lora_rank"),
        (("lora_alpha",), "--lora_alpha"),
        (("lora_dropout",), "--lora_dropout"),
        (("lora_target",), "--lora_target"),
        (("quantization_bit",), "--quantization_bit"),
        (("quantization_method",), "--quantization_method"),
        (("double_quantization",), "--double_quantization"),
    )
    for aliases, cli_flag in option_mapping:
        append_option(cli_flag, get_config_value(*aliases))

    return command


def run_remote_fine_tune(
    *,
    api_base_url,
    fine_tune_run_id,
    token,
    work_dir,
    dry_run=False,
    deployment_endpoint="",
    deployment_model_name="",
):
    """在本地 Runner 上执行完整的微调训练流程。

    流程：
    1. fetch_runner_spec - 从平台拉取执行规格
    2. materialize_export_bundle - 下载训练数据集
    3. build_llamafactory_command - 构建训练命令
    4. (若不是 dry_run) 执行 subprocess 运行训练
    5. 上报 running/succeeded/failed 状态到平台

    类比 SpringBoot 中一个编排完整远程任务生命周期的 @Async Service 方法。

    参数:
        api_base_url: str，平台 API 基础地址。
        fine_tune_run_id: int，微调运行 ID。
        token: str，回调令牌。
        work_dir: str，本地工作目录。
        dry_run: bool，若为 True 则只构建命令不实际执行训练。
        deployment_endpoint: str，部署端点（成功后回传给平台）。
        deployment_model_name: str，部署模型名（成功后回传给平台）。

    返回:
        dict，包含 spec、export_dir、output_dir、command 和 callback_payload。

    异常:
        subprocess.CalledProcessError: 当训练命令执行失败时抛出。
    """
    spec = fetch_runner_spec(
        api_base_url=api_base_url,
        fine_tune_run_id=fine_tune_run_id,
        token=token,
    )
    export_dir = materialize_export_bundle(spec=spec, work_dir=work_dir)
    output_dir = Path(work_dir) / spec["run_key"] / "artifacts"
    output_dir.mkdir(parents=True, exist_ok=True)
    command = build_llamafactory_command(
        spec=spec,
        export_dir=export_dir,
        output_dir=str(output_dir),
    )

    if dry_run:
        return {
            "spec": spec,
            "export_dir": export_dir,
            "output_dir": str(output_dir),
            "command": command,
        }

    external_job_id = f"local-llamafactory-{spec['run_key']}"
    report_runner_status(
        api_base_url=api_base_url,
        fine_tune_run_id=fine_tune_run_id,
        token=token,
        payload={"status": "running", "external_job_id": external_job_id},
    )

    try:
        subprocess.run(command, check=True, cwd=export_dir)
    except subprocess.CalledProcessError as exc:
        report_runner_status(
            api_base_url=api_base_url,
            fine_tune_run_id=fine_tune_run_id,
            token=token,
            payload={"status": "failed", "external_job_id": external_job_id, "failure_reason": str(exc)},
        )
        raise

    callback_payload = {
        "status": "succeeded",
        "external_job_id": external_job_id,
        "artifact_manifest": {"adapter_path": str(output_dir)},
    }
    if deployment_endpoint:
        callback_payload["deployment_endpoint"] = deployment_endpoint
    if deployment_model_name:
        callback_payload["deployment_model_name"] = deployment_model_name
    report_runner_status(
        api_base_url=api_base_url,
        fine_tune_run_id=fine_tune_run_id,
        token=token,
        payload=callback_payload,
    )
    return {
        "spec": spec,
        "export_dir": export_dir,
        "output_dir": str(output_dir),
        "command": command,
        "callback_payload": callback_payload,
    }
