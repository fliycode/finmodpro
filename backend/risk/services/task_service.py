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
    }

    if task.celery_task_id:
        payload["celery_task_id"] = task.celery_task_id
    if task.status == RiskExtractionTask.STATUS_SUCCEEDED:
        payload["result"] = task.result_payload

    return payload


def submit_risk_extraction(document):
    from risk.tasks import extract_document_task

    broker_url = str(getattr(settings, "CELERY_BROKER_URL", "") or "")
    should_run_inline = settings.CELERY_TASK_ALWAYS_EAGER
    should_run_in_process = not should_run_inline and broker_url.startswith("memory://")

    with transaction.atomic():
        locked_document = Document.objects.select_for_update().get(id=document.id)
        latest_task = locked_document.risk_extraction_tasks.order_by("created_at", "id").last()
        if latest_task and latest_task.status in {
            RiskExtractionTask.STATUS_QUEUED,
            RiskExtractionTask.STATUS_RUNNING,
        }:
            return latest_task, False

        task = RiskExtractionTask.objects.create(
            document=locked_document,
            status=RiskExtractionTask.STATUS_QUEUED,
            current_step=RiskExtractionTask.STEP_QUEUED,
            progress=6,
            message="风险抽取任务已排队。",
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
    task.current_step = RiskExtractionTask.STEP_EXTRACTING
    task.progress = 72
    task.message = "正在分析文档中的风险事件。"
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


def finish_risk_extraction_task(task, *, status, message, result_payload=None):
    task.status = status
    task.current_step = (
        RiskExtractionTask.STEP_COMPLETED
        if status == RiskExtractionTask.STATUS_SUCCEEDED
        else RiskExtractionTask.STEP_FAILED
    )
    task.progress = 100
    task.message = message
    task.error_message = "" if status == RiskExtractionTask.STATUS_SUCCEEDED else message
    task.result_payload = result_payload or {}
    task.created_count = int((result_payload or {}).get("created_count", 0))
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
