"""
风险提取任务管理服务 —— 管理 RiskExtractionTask 的完整生命周期。
类比 SpringBoot: 相当于 @Service 中的异步任务管理器，
负责任务的提交、启动、心跳更新、完成和过期处理。

核心流程:
- submit_risk_extraction:     提交任务（含防重复检测和并发限制）
- start_risk_extraction_task: 标记任务开始执行
- heartbeat_risk_extraction_task: 更新任务进度
- finish_risk_extraction_task:    标记任务完成/失败
- expire_stale_risk_extractions:  清理超时任务
"""

from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from common.background_jobs import run_background_job
from knowledgebase.models import Document
from risk.models import RiskExtractionTask

# 任务状态到 Celery 状态标签的映射
STATUS_LABELS = {
    RiskExtractionTask.STATUS_QUEUED: "QUEUED",
    RiskExtractionTask.STATUS_RUNNING: "RUNNING",
    RiskExtractionTask.STATUS_SUCCEEDED: "SUCCESS",
    RiskExtractionTask.STATUS_FAILED: "FAILURE",
}


class RiskExtractionBusyError(Exception):
    """
    队列繁忙异常 —— 当同时运行的任务数达到上限时抛出。

    类比 SpringBoot: 相当于自定义的 @ResponseStatus(HttpStatus.TOO_MANY_REQUESTS) 异常。
    """
    code = RiskExtractionTask.ERROR_BUSY
    status_code = 429

    def __init__(self, message="风险提取队列繁忙，请稍后再试。"):
        super().__init__(message)
        self.message = message


def _resolve_queue_timeout_seconds():
    """从配置读取排队超时秒数，最小 30 秒。"""
    configured = int(getattr(settings, "RISK_EXTRACTION_QUEUE_TIMEOUT_SECONDS", 180) or 180)
    return max(30, configured)


def _resolve_stage_timeout_seconds():
    """从配置读取阶段超时秒数，最小 30 秒。"""
    configured = int(getattr(settings, "RISK_EXTRACTION_STAGE_TIMEOUT_SECONDS", 75) or 75)
    return max(30, configured)


def _resolve_submission_limit():
    """从配置读取同时运行的任务上限，最小 1。"""
    configured = int(getattr(settings, "RISK_EXTRACTION_SUBMISSION_LIMIT", 2) or 2)
    return max(1, configured)


def _task_timeout_seconds(task):
    """
    根据任务当前步骤返回对应的超时秒数。

    参数:
        task (RiskExtractionTask): 任务实例。

    返回:
        int: 超时秒数（排队阶段用队列超时，其他阶段用阶段超时）。
    """
    if task.current_step == RiskExtractionTask.STEP_QUEUED:
        return _resolve_queue_timeout_seconds()
    return _resolve_stage_timeout_seconds()


def _is_task_stale(task):
    """
    判断任务是否已过期。

    参数:
        task (RiskExtractionTask): 任务实例。

    返回:
        bool: 最后更新时间超过超时阈值则为 True。
    """
    if task is None or task.updated_at is None:
        return False
    deadline = timezone.now() - timedelta(seconds=_task_timeout_seconds(task))
    return task.updated_at <= deadline


def _build_failure_payload(*, task, error_code):
    """构建任务失败时的 result_payload。"""
    payload = dict(task.result_payload or {})
    payload["error_code"] = error_code
    payload["failed_step"] = task.current_step
    return payload


def _expire_stale_task(task):
    """
    将过期任务标记为失败。

    参数:
        task (RiskExtractionTask): 过期任务实例。
    """
    is_queue_timeout = task.current_step == RiskExtractionTask.STEP_QUEUED
    error_code = (
        RiskExtractionTask.ERROR_QUEUE_TIMEOUT
        if is_queue_timeout
        else RiskExtractionTask.ERROR_STAGE_TIMEOUT
    )
    message = (
        "风险提取排队超时，系统繁忙，请稍后重试。"
        if is_queue_timeout
        else "风险提取执行超时，已自动终止。"
    )
    task.status = RiskExtractionTask.STATUS_FAILED
    task.current_step = RiskExtractionTask.STEP_FAILED
    task.progress = 100
    task.message = message
    task.error_message = message
    task.result_payload = _build_failure_payload(task=task, error_code=error_code)
    task.created_count = 0
    task.finished_at = timezone.now()
    task.save(
        update_fields=[
            "status", "current_step", "progress", "message", "error_message",
            "result_payload", "created_count", "finished_at", "updated_at",
        ]
    )


def expire_stale_risk_extractions():
    """
    扫描并清理所有已过期的排队/运行中任务。

    类比 SpringBoot: 相当于 @Scheduled 定时清理方法。

    返回:
        int: 清理的过期任务数量。
    """
    expired_count = 0
    with transaction.atomic():
        active_tasks = list(
            RiskExtractionTask.objects.select_for_update()
            .filter(status__in=[RiskExtractionTask.STATUS_QUEUED, RiskExtractionTask.STATUS_RUNNING])
            .order_by("created_at", "id")
        )
        for task in active_tasks:
            if not _is_task_stale(task):
                continue
            _expire_stale_task(task)
            expired_count += 1
    return expired_count


def _resolve_error_code(task):
    """从任务 result_payload 中提取错误码。"""
    return str((task.result_payload or {}).get("error_code") or "")


def get_risk_extraction_failure_status_code(task):
    """
    根据任务失败的错误码，映射为 HTTP 状态码。

    参数:
        task (RiskExtractionTask): 任务实例。

    返回:
        int: 超时类错误返回 504，其他返回 500。
    """
    error_code = _resolve_error_code(task)
    if error_code in {
        RiskExtractionTask.ERROR_TIMEOUT,
        RiskExtractionTask.ERROR_QUEUE_TIMEOUT,
        RiskExtractionTask.ERROR_STAGE_TIMEOUT,
    }:
        return 504
    return 500


def serialize_risk_extraction_task(task):
    """
    将 RiskExtractionTask 实例序列化为前端可用的字典。

    参数:
        task (RiskExtractionTask | None): 任务实例。

    返回:
        dict | None: 序列化后的任务数据，None 输入返回 None。
    """
    if task is None:
        return None

    payload = {
        "task_id": str(task.id),
        "document_id": task.document_id,
        "status": STATUS_LABELS.get(task.status, str(task.status or "").upper()),
        "step": task.current_step,
        "progress": task.progress,
        "created_count": task.created_count,
        "message": task.message or "",
        "error_message": task.error_message or "",
        "started_at": task.started_at.isoformat() if task.started_at else None,
        "finished_at": task.finished_at.isoformat() if task.finished_at else None,
        "created_at": task.created_at.isoformat(),
        "updated_at": task.updated_at.isoformat(),
        "error_code": _resolve_error_code(task),
    }

    if task.celery_task_id:
        payload["celery_task_id"] = task.celery_task_id
    if task.status == RiskExtractionTask.STATUS_SUCCEEDED:
        payload["result"] = task.result_payload

    return payload


def _active_task_count():
    """获取当前活跃任务数（排队 + 运行中）。"""
    return RiskExtractionTask.objects.filter(
        status__in=[RiskExtractionTask.STATUS_QUEUED, RiskExtractionTask.STATUS_RUNNING]
    ).count()


def submit_risk_extraction(document):
    """
    提交一个风险提取任务。

    包含以下逻辑:
    1. 清理过期任务
    2. 检查是否有重复的活跃任务
    3. 检查并发限制
    4. 创建新任务
    5. 根据执行模式（inline / in-process / celery）启动任务

    类比 SpringBoot: 相当于 @Async 方法的提交逻辑。

    参数:
        document (Document): 要提取的文档实例。

    返回:
        tuple: (task, created) — task 为任务实例, created 为是否新创建。

    抛出:
        RiskExtractionBusyError: 当并发任务数达到上限时。
    """
    from risk.tasks import extract_document_task

    broker_url = str(getattr(settings, "CELERY_BROKER_URL", "") or "")
    should_run_inline = settings.CELERY_TASK_ALWAYS_EAGER
    should_run_in_process = not should_run_inline and broker_url.startswith("memory://")

    expire_stale_risk_extractions()

    with transaction.atomic():
        locked_document = Document.objects.select_for_update().get(id=document.id)
        latest_task = (
            RiskExtractionTask.objects.select_for_update()
            .filter(document=locked_document)
            .order_by("created_at", "id")
            .last()
        )
        if latest_task and latest_task.status in {
            RiskExtractionTask.STATUS_QUEUED,
            RiskExtractionTask.STATUS_RUNNING,
        }:
            if not _is_task_stale(latest_task):
                return latest_task, False
            _expire_stale_task(latest_task)

        if _active_task_count() >= _resolve_submission_limit():
            raise RiskExtractionBusyError()

        task = RiskExtractionTask.objects.create(
            document=locked_document,
            status=RiskExtractionTask.STATUS_QUEUED,
            current_step=RiskExtractionTask.STEP_QUEUED,
            progress=6,
            message="风险抽取任务已排队。",
            result_payload={},
        )

    try:
        if should_run_inline:
            async_result = extract_document_task.apply(args=(locked_document.id, str(task.id)))
        elif should_run_in_process:
            run_background_job(
                name=f"risk-extract-{task.id}",
                target=extract_document_task,
                args=(locked_document.id, str(task.id)),
            )
            async_result = type("InProcessTaskResult", (), {"id": f"local-risk:{task.id}"})()
        else:
            async_result = extract_document_task.delay(locked_document.id, str(task.id))
    except Exception as exc:
        finish_risk_extraction_task(
            task,
            status=RiskExtractionTask.STATUS_FAILED,
            message=str(exc) or "风险抽取任务提交失败。",
        )
        raise

    task.celery_task_id = async_result.id or ""
    task.save(update_fields=["celery_task_id", "updated_at"])
    return task, True


def start_risk_extraction_task(task):
    """
    将任务状态从 queued 更新为 running，开始执行。

    参数:
        task (RiskExtractionTask): 要启动的任务实例。
    """
    task.status = RiskExtractionTask.STATUS_RUNNING
    task.current_step = RiskExtractionTask.STEP_RETRIEVING
    task.progress = 12
    task.message = "正在准备检索风险相关内容。"
    task.error_message = ""
    task.started_at = timezone.now()
    task.finished_at = None
    task.save(
        update_fields=[
            "status", "current_step", "progress", "message", "error_message",
            "started_at", "finished_at", "updated_at",
        ]
    )


def heartbeat_risk_extraction_task(task, *, step, progress, message):
    """
    更新任务的心跳（当前步骤和进度）。

    类比 SpringBoot: 相当于异步任务的进度报告回调。

    参数:
        task (RiskExtractionTask): 任务实例。
        step (str): 当前步骤标识。
        progress (int): 进度百分比。
        message (str): 状态消息。
    """
    task.status = RiskExtractionTask.STATUS_RUNNING
    task.current_step = step
    task.progress = progress
    task.message = message
    if task.started_at is None:
        task.started_at = timezone.now()
    task.save(
        update_fields=["status", "current_step", "progress", "message", "started_at", "updated_at"]
    )


def list_extraction_tasks(*, document_id=None, status=None, limit=20):
    """
    查询提取任务列表，按创建时间倒序。

    参数:
        document_id (int, 可选): 按文档 ID 过滤。
        status (str, 可选): 按状态过滤 (queued / running / succeeded / failed)。
        limit (int): 返回条数上限。

    返回:
        QuerySet[RiskExtractionTask]: 带 document 预加载的查询集。
    """
    queryset = RiskExtractionTask.objects.select_related("document").order_by("-created_at")
    if document_id is not None:
        queryset = queryset.filter(document_id=document_id)
    if status is not None:
        queryset = queryset.filter(status=status)
    return queryset[:limit]


def finish_risk_extraction_task(task, *, status, message, result_payload=None, error_code=""):
    """
    标记任务完成（成功或失败），写入最终结果。

    类比 SpringBoot: 相当于 @Async 方法的回调/完成处理。

    参数:
        task (RiskExtractionTask): 任务实例。
        status (str): 最终状态（succeeded / failed）。
        message (str): 完成/错误消息。
        result_payload (dict, 可选): 结果数据。
        error_code (str, 可选): 错误码。
    """
    payload = dict(result_payload or {})
    if status != RiskExtractionTask.STATUS_SUCCEEDED and error_code:
        payload["error_code"] = error_code
        payload["failed_step"] = task.current_step

    task.status = status
    task.current_step = (
        RiskExtractionTask.STEP_COMPLETED
        if status == RiskExtractionTask.STATUS_SUCCEEDED
        else RiskExtractionTask.STEP_FAILED
    )
    task.progress = 100
    task.message = message
    task.error_message = "" if status == RiskExtractionTask.STATUS_SUCCEEDED else message
    task.result_payload = payload
    task.created_count = int(payload.get("created_count", 0))
    task.finished_at = timezone.now()
    task.save(
        update_fields=[
            "status", "current_step", "progress", "message", "error_message",
            "result_payload", "created_count", "finished_at", "updated_at",
        ]
    )
