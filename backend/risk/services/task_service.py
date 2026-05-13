from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from common.background_jobs import run_background_job
from knowledgebase.models import Document
from risk.models import RiskExtractionTask

STATUS_LABELS = {
    RiskExtractionTask.STATUS_QUEUED: "QUEUED",
    RiskExtractionTask.STATUS_RUNNING: "RUNNING",
    RiskExtractionTask.STATUS_SUCCEEDED: "SUCCESS",
    RiskExtractionTask.STATUS_FAILED: "FAILURE",
}


class RiskExtractionBusyError(Exception):
    code = RiskExtractionTask.ERROR_BUSY
    status_code = 429

    def __init__(self, message="风险提取队列繁忙，请稍后再试。"):
        super().__init__(message)
        self.message = message


def _resolve_queue_timeout_seconds():
    configured = int(getattr(settings, "RISK_EXTRACTION_QUEUE_TIMEOUT_SECONDS", 180) or 180)
    return max(30, configured)


def _resolve_stage_timeout_seconds():
    configured = int(getattr(settings, "RISK_EXTRACTION_STAGE_TIMEOUT_SECONDS", 75) or 75)
    return max(30, configured)


def _resolve_submission_limit():
    configured = int(getattr(settings, "RISK_EXTRACTION_SUBMISSION_LIMIT", 2) or 2)
    return max(1, configured)


def _task_timeout_seconds(task):
    if task.current_step == RiskExtractionTask.STEP_QUEUED:
        return _resolve_queue_timeout_seconds()
    return _resolve_stage_timeout_seconds()


def _is_task_stale(task):
    if task is None or task.updated_at is None:
        return False
    deadline = timezone.now() - timedelta(seconds=_task_timeout_seconds(task))
    return task.updated_at <= deadline


def _build_failure_payload(*, task, error_code):
    payload = dict(task.result_payload or {})
    payload["error_code"] = error_code
    payload["failed_step"] = task.current_step
    return payload


def _expire_stale_task(task):
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
            "status",
            "current_step",
            "progress",
            "message",
            "error_message",
            "result_payload",
            "created_count",
            "finished_at",
            "updated_at",
        ]
    )


def expire_stale_risk_extractions():
    expired_count = 0
    with transaction.atomic():
        active_tasks = list(
            RiskExtractionTask.objects.select_for_update()
            .filter(
                status__in=[
                    RiskExtractionTask.STATUS_QUEUED,
                    RiskExtractionTask.STATUS_RUNNING,
                ]
            )
            .order_by("created_at", "id")
        )
        for task in active_tasks:
            if not _is_task_stale(task):
                continue
            _expire_stale_task(task)
            expired_count += 1
    return expired_count


def _resolve_error_code(task):
    return str((task.result_payload or {}).get("error_code") or "")


def get_risk_extraction_failure_status_code(task):
    error_code = _resolve_error_code(task)
    if error_code in {
        RiskExtractionTask.ERROR_TIMEOUT,
        RiskExtractionTask.ERROR_QUEUE_TIMEOUT,
        RiskExtractionTask.ERROR_STAGE_TIMEOUT,
    }:
        return 504
    return 500


def serialize_risk_extraction_task(task):
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
    return RiskExtractionTask.objects.filter(
        status__in=[
            RiskExtractionTask.STATUS_QUEUED,
            RiskExtractionTask.STATUS_RUNNING,
        ]
    ).count()


def submit_risk_extraction(document):
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
    task.status = RiskExtractionTask.STATUS_RUNNING
    task.current_step = RiskExtractionTask.STEP_RETRIEVING
    task.progress = 12
    task.message = "正在准备检索风险相关内容。"
    task.error_message = ""
    task.started_at = timezone.now()
    task.finished_at = None
    task.save(
        update_fields=[
            "status",
            "current_step",
            "progress",
            "message",
            "error_message",
            "started_at",
            "finished_at",
            "updated_at",
        ]
    )


def heartbeat_risk_extraction_task(task, *, step, progress, message):
    task.status = RiskExtractionTask.STATUS_RUNNING
    task.current_step = step
    task.progress = progress
    task.message = message
    if task.started_at is None:
        task.started_at = timezone.now()
    task.save(
        update_fields=[
            "status",
            "current_step",
            "progress",
            "message",
            "started_at",
            "updated_at",
        ]
    )


def finish_risk_extraction_task(task, *, status, message, result_payload=None, error_code=""):
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
            "status",
            "current_step",
            "progress",
            "message",
            "error_message",
            "result_payload",
            "created_count",
            "finished_at",
            "updated_at",
        ]
    )
