from celery import shared_task
from celery.exceptions import SoftTimeLimitExceeded
from django.conf import settings

from knowledgebase.models import Document
from risk.models import RiskExtractionTask
from risk.serializers import RiskEventSummarySerializer
from risk.services.extraction_service import (
    detect_risk_signals,
    extract_risk_events_for_document,
    list_document_chunks,
)
from risk.services.task_service import (
    expire_stale_risk_extractions,
    finish_risk_extraction_task,
    heartbeat_risk_extraction_task,
    start_risk_extraction_task,
)


def _resolve_extraction_task(extraction_task_id):
    if extraction_task_id is None:
        return None
    try:
        return RiskExtractionTask.objects.get(id=extraction_task_id)
    except RiskExtractionTask.DoesNotExist:
        return None


def _finalize_success(extraction_task, result):
    if extraction_task is None:
        return
    finish_risk_extraction_task(
        extraction_task,
        status=RiskExtractionTask.STATUS_SUCCEEDED,
        message=result["message"],
        result_payload=result,
    )


def _finalize_failure(extraction_task, *, message, error_code):
    if extraction_task is None:
        return
    finish_risk_extraction_task(
        extraction_task,
        status=RiskExtractionTask.STATUS_FAILED,
        message=message,
        error_code=error_code,
    )


@shared_task(
    name="risk.extract_document_task",
    soft_time_limit=settings.RISK_EXTRACTION_TASK_SOFT_TIME_LIMIT,
    time_limit=settings.RISK_EXTRACTION_TASK_TIME_LIMIT,
)
def extract_document_task(document_id, extraction_task_id=None):
    extraction_task = _resolve_extraction_task(extraction_task_id)

    try:
        document = Document.objects.get(id=document_id)
    except Document.DoesNotExist:
        result = {
            "status": "not_found",
            "message": "文档不存在。",
            "created_count": 0,
            "risk_events": [],
        }
        _finalize_failure(
            extraction_task,
            message=result["message"],
            error_code=RiskExtractionTask.ERROR_TASK_MISSING,
        )
        return result

    if extraction_task is not None:
        start_risk_extraction_task(extraction_task)

    chunks = list_document_chunks(document=document)
    if not chunks:
        result = {
            "status": "no_chunks",
            "message": "文档暂无可抽取内容。",
            "created_count": 0,
            "risk_events": [],
            "document_id": document.id,
        }
        _finalize_success(extraction_task, result)
        return result

    signal_summary = detect_risk_signals(document=document, chunks=chunks)
    if not signal_summary["has_signal"]:
        result = {
            "status": "no_signals",
            "message": "文档未检测到金融风险相关信号，已跳过风险抽取。",
            "created_count": 0,
            "risk_events": [],
            "document_id": document.id,
            "signal_summary": signal_summary,
        }
        _finalize_success(extraction_task, result)
        return result

    try:
        created_events = extract_risk_events_for_document(
            document=document,
            stage_callback=(
                (lambda **kwargs: heartbeat_risk_extraction_task(extraction_task, **kwargs))
                if extraction_task is not None
                else None
            ),
        )
    except SoftTimeLimitExceeded:
        message = "风险抽取执行超时，已自动终止。"
        result = {
            "status": "failed",
            "message": message,
            "created_count": 0,
            "risk_events": [],
            "document_id": document.id,
            "error_code": RiskExtractionTask.ERROR_TIMEOUT,
        }
        _finalize_failure(
            extraction_task,
            message=message,
            error_code=RiskExtractionTask.ERROR_TIMEOUT,
        )
        return result
    except Exception as exc:
        result = {
            "status": "failed",
            "message": str(exc) or "风险抽取失败。",
            "created_count": 0,
            "risk_events": [],
            "document_id": document.id,
        }
        _finalize_failure(
            extraction_task,
            message=result["message"],
            error_code=RiskExtractionTask.ERROR_TIMEOUT
            if "timeout" in str(exc).lower()
            else "",
        )
        return result

    result = {
        "status": "succeeded",
        "message": "风险抽取完成。",
        "document_id": document.id,
        "created_count": len(created_events),
        "risk_events": RiskEventSummarySerializer(created_events, many=True).data,
    }
    _finalize_success(extraction_task, result)
    return result


@shared_task(
    name="risk.batch_extract_document_task",
    soft_time_limit=settings.RISK_EXTRACTION_BATCH_TASK_SOFT_TIME_LIMIT,
    time_limit=settings.RISK_EXTRACTION_BATCH_TASK_TIME_LIMIT,
)
def batch_extract_document_task(document_ids):
    normalized_document_ids = list(dict.fromkeys(document_ids))
    documents_by_id = {
        document.id: document
        for document in Document.objects.filter(id__in=normalized_document_ids)
    }

    results = []
    total_created_count = 0
    for document_id in normalized_document_ids:
        document = documents_by_id.get(document_id)
        if document is None:
            results.append({
                "document_id": document_id,
                "status": "not_found",
                "message": "文档不存在。",
                "created_count": 0,
                "risk_events": [],
            })
            continue

        chunks = list_document_chunks(document=document)
        if not chunks:
            results.append({
                "document_id": document.id,
                "status": "no_chunks",
                "message": "文档暂无可抽取内容。",
                "created_count": 0,
                "risk_events": [],
            })
            continue

        signal_summary = detect_risk_signals(document=document, chunks=chunks)
        if not signal_summary["has_signal"]:
            results.append({
                "document_id": document.id,
                "status": "no_signals",
                "message": "文档未检测到金融风险相关信号，已跳过风险抽取。",
                "created_count": 0,
                "risk_events": [],
            })
            continue

        try:
            created_events = extract_risk_events_for_document(document=document)
        except SoftTimeLimitExceeded:
            results.append({
                "document_id": document.id,
                "status": "failed",
                "message": "批量风险抽取执行超时。",
                "created_count": 0,
                "risk_events": [],
                "error_code": RiskExtractionTask.ERROR_TIMEOUT,
            })
            continue
        except Exception as exc:
            results.append({
                "document_id": document.id,
                "status": "failed",
                "message": str(exc) or "风险抽取失败。",
                "created_count": 0,
                "risk_events": [],
            })
            continue

        total_created_count += len(created_events)
        results.append({
            "document_id": document.id,
            "status": "created" if created_events else "completed",
            "message": "风险抽取完成。" if created_events else "未识别到风险事件。",
            "created_count": len(created_events),
            "risk_events": RiskEventSummarySerializer(created_events, many=True).data,
        })

    return {
        "total_documents": len(normalized_document_ids),
        "processed_documents": len(results),
        "total_created_count": total_created_count,
        "results": results,
    }


@shared_task(name="risk.expire_stale_extractions_task")
def expire_stale_extractions_task():
    expired_count = expire_stale_risk_extractions()
    return {"expired_count": expired_count}
