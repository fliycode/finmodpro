"""
微调回调服务（类比 SpringBoot 中 @Service 的异步回调处理层）。

负责：
- 回调令牌的 HMAC-SHA256 哈希与验证（类比 Spring Security 的 Token 校验）
- 微调运行结束后自动注册候选模型配置（将微调产物映射为可用模型）
- 将远程 Runner 的回调 payload 映射到 FineTuneRun 模型字段

类比 SpringBoot 中接收外部 Webhook 回调的 Service，负责验签、状态转换和后续动作触发。
"""
import hashlib
import hmac

from django.conf import settings
from django.utils import timezone

from llm.models import FineTuneRun, ModelConfig


def hash_callback_token(token):
    """对回调令牌进行 HMAC-SHA256 哈希，用于安全存储。

    类似 SpringBoot 中使用 BCryptPasswordEncoder 或 HMAC 对敏感令牌做单向哈希存储。

    参数:
        token: str，原始回调令牌明文。

    返回:
        str，十六进制编码的 HMAC-SHA256 哈希值。
    """
    secret = settings.FINE_TUNE_CALLBACK_SECRET.encode("utf-8")
    return hmac.new(secret, token.encode("utf-8"), hashlib.sha256).hexdigest()


def verify_callback_token(*, fine_tune_run, token):
    """验证传入的回调令牌是否与存储的哈希值匹配。

    使用 hmac.compare_digest 做常量时间比较（防止时序攻击）。

    参数:
        fine_tune_run: FineTuneRun 实例，包含存储的 callback_token_hash。
        token: str，待验证的原始令牌。

    返回:
        bool，True 表示令牌有效，False 表示无效或缺失。
    """
    if not token or not fine_tune_run.callback_token_hash:
        return False
    expected_hash = hash_callback_token(token)
    return hmac.compare_digest(expected_hash, fine_tune_run.callback_token_hash)


def register_candidate_model_config(*, fine_tune_run):
    """微调成功后，将产物注册为一个可用的 OpenAI 兼容模型配置。

    若该微调运行已注册过则直接返回已有配置（幂等性）。
    新配置的名称格式为 "{基础模型名}-{run_key}"，截断至 255 字符。

    类比 SpringBoot 中微服务部署成功后自动向服务注册中心（如 Eureka/Nacos）注册实例。

    参数:
        fine_tune_run: FineTuneRun 实例，包含 deployment_endpoint 和 deployment_model_name。

    返回:
        ModelConfig 实例或 None（当缺少 endpoint 或 model_name 时返回 None）。
    """
    if fine_tune_run.registered_model_config_id:
        return fine_tune_run.registered_model_config

    endpoint = fine_tune_run.deployment_endpoint.strip()
    model_name = fine_tune_run.deployment_model_name.strip()
    if not endpoint or not model_name:
        return None

    config_name = f"{fine_tune_run.base_model.name}-{fine_tune_run.run_key}"
    model_config = ModelConfig.objects.create(
        name=config_name[:255],
        capability=fine_tune_run.base_model.capability,
        provider=ModelConfig.PROVIDER_OPENAI_COMPATIBLE,
        model_name=model_name,
        endpoint=endpoint,
        options={},
        is_active=False,
    )
    fine_tune_run.registered_model_config = model_config
    fine_tune_run.save(update_fields=["registered_model_config", "updated_at"])
    return model_config


def apply_runner_callback(*, fine_tune_run, payload):
    """将远程 Runner 的回调数据应用到 FineTuneRun 记录。

    处理逻辑：
    - 更新 external_job_id、deployment_endpoint、deployment_model_name、failure_reason
    - 状态转换：incoming_status -> running/succeeded/failed（并自动记录时间戳）
    - 记录 metrics 和 artifact_manifest
    - 成功后自动注册候选模型配置

    类比 SpringBoot 中处理 Webhook 回调的 Service 方法，负责状态机转换和数据持久化。

    参数:
        fine_tune_run: FineTuneRun 实例，接收回调的微调运行记录。
        payload: dict，Runner 发来的回调数据，可包含：
            - external_job_id: 外部任务 ID
            - deployment_endpoint: 部署端点
            - deployment_model_name: 部署模型名
            - failure_reason: 失败原因
            - status: 新状态
            - metrics: 训练指标
            - artifact_manifest: 产物清单

    返回:
        FineTuneRun 实例，更新后的（已 refresh_from_db）微调运行记录。
    """
    now = timezone.now()
    for key in ("external_job_id", "deployment_endpoint", "deployment_model_name", "failure_reason"):
        if key in payload:
            setattr(fine_tune_run, key, payload.get(key) or "")

    incoming_status = payload.get("status")
    if incoming_status:
        fine_tune_run.status = incoming_status
        if incoming_status == FineTuneRun.STATUS_RUNNING and fine_tune_run.started_at is None:
            fine_tune_run.started_at = now
        if incoming_status in {FineTuneRun.STATUS_SUCCEEDED, FineTuneRun.STATUS_FAILED}:
            fine_tune_run.finished_at = now

    if "metrics" in payload:
        fine_tune_run.metrics = payload.get("metrics") or {}
    if "artifact_manifest" in payload:
        fine_tune_run.artifact_manifest = payload.get("artifact_manifest") or {}
        adapter_path = fine_tune_run.artifact_manifest.get("adapter_path", "")
        if adapter_path and not fine_tune_run.artifact_path:
            fine_tune_run.artifact_path = adapter_path

    fine_tune_run.last_heartbeat_at = now
    fine_tune_run.save()

    if fine_tune_run.status == FineTuneRun.STATUS_SUCCEEDED:
        register_candidate_model_config(fine_tune_run=fine_tune_run)

    fine_tune_run.refresh_from_db()
    return fine_tune_run
