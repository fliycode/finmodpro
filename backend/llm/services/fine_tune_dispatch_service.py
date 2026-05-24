"""
微调调度服务（类比 SpringBoot 中 @Service 的远程作业提交层）。

负责将本地的微调运行任务通过 HTTP 派发到远程训练服务器（LLaMA-Factory Runner）。
执行前会校验 Runner 服务器是否启用、回调令牌是否就绪等前置条件。

类比 SpringBoot 中通过 RestTemplate 或 WebClient 向远程微服务提交异步任务的 Service。
"""
import json
from urllib import error, request

from django.utils import timezone

from llm.services.fine_tune_export_service import get_runner_execution_spec


def submit_fine_tune_run(*, fine_tune_run, request_context):
    """将微调任务提交到远程训练服务器执行。

    流程：
    1. 校验 runner_server 存在且启用
    2. 校验 callback_token_value 就绪
    3. 通过 get_runner_execution_spec 构建完整的训练规格 payload
    4. 向 Runner 的 POST /api/v1/fine-tune-jobs 发起 HTTP 请求
    5. 将响应中的 external_job_id 回写到 fine_tune_run

    类比 SpringBoot 中通过 @Async 或 RestTemplate 将任务派发到远程 Worker 节点的 Service 方法。

    参数:
        fine_tune_run: FineTuneRun 实例，包含 runner_server 和 callback_token_value。
        request_context: HttpRequest 实例，用于构建回调 URL 和 API base URL。

    返回:
        dict，包含：
        - dispatch: dict，调度结果（job_id、status、runner_name）
        - fine_tune_run: FineTuneRun 实例（已 refresh_from_db）

    异常:
        ValueError: 当训练服务器未绑定、已停用或缺少回调令牌时抛出。
        RuntimeError: 当远程服务器返回 HTTP 错误或连接失败时抛出。
    """
    runner_server = fine_tune_run.runner_server
    if runner_server is None:
        raise ValueError("微调任务尚未绑定训练服务器。")
    if not runner_server.is_enabled:
        raise ValueError("训练服务器已停用。")
    if not fine_tune_run.callback_token_value:
        raise ValueError("微调任务缺少可回放的回调令牌。")

    dispatch_payload = get_runner_execution_spec(
        fine_tune_run=fine_tune_run,
        request=request_context,
        include_callback_token=True,
    )
    dispatch_url = f"{runner_server.base_url.rstrip('/')}/api/v1/fine-tune-jobs"
    headers = {"Content-Type": "application/json"}
    if runner_server.auth_token:
        headers["Authorization"] = f"Bearer {runner_server.auth_token}"

    try:
        response = request.urlopen(
            request.Request(
                dispatch_url,
                data=json.dumps(dispatch_payload, ensure_ascii=False).encode("utf-8"),
                headers=headers,
                method="POST",
            ),
            timeout=30,
        )
    except error.HTTPError as exc:
        raise RuntimeError(f"远程训练服务器返回错误：{exc.code}") from exc
    except error.URLError as exc:
        raise RuntimeError("无法连接远程训练服务器。") from exc

    response_payload = json.loads(response.read().decode("utf-8"))
    dispatch_result = response_payload.get("data") or response_payload
    external_job_id = dispatch_result.get("job_id") or dispatch_result.get("external_job_id") or ""
    runner_name = dispatch_result.get("runner_name") or fine_tune_run.runner_name or runner_server.name

    fine_tune_run.external_job_id = external_job_id
    fine_tune_run.runner_name = runner_name[:128]
    fine_tune_run.queued_at = fine_tune_run.queued_at or timezone.now()
    fine_tune_run.save(update_fields=["external_job_id", "runner_name", "queued_at", "updated_at"])
    fine_tune_run.refresh_from_db()

    return {
        "dispatch": {
            "job_id": external_job_id,
            "status": dispatch_result.get("status") or "",
            "runner_name": runner_name,
        },
        "fine_tune_run": fine_tune_run,
    }
