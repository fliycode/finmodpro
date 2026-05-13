from celery import shared_task

from knowledgebase.models import Document
from risk.models import RiskExtractionTask
from risk.serializers import RiskEventSummarySerializer
from risk.services.extraction_service import (
    extract_risk_events_for_document,
    list_document_chunks,
)
from risk.services.task_service import finish_risk_extraction_task, start_risk_extraction_task


@shared_task(name="risk.extract_document_task")
def extract_document_task(document_id, extraction_task_id=None):
    extraction_task = None
    if extraction_task_id is not None:
        try:
            extraction_task = RiskExtractionTask.objects.get(id=extraction_task_id)
        except RiskExtractionTask.DoesNotExist:
            extraction_task = None

    try:
        document = Document.objects.get(id=document_id)
    except Document.DoesNotExist:
        result = {"status": "not_found", "message": "文档不存在。", "created_count": 0, "risk_events": []}
        if extraction_task is not None:
            finish_risk_extraction_task(
                extraction_task,
                status=RiskExtractionTask.STATUS_FAILED,
                message=result["message"],
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
        if extraction_task is not None:
            finish_risk_extraction_task(
                extraction_task,
                status=RiskExtractionTask.STATUS_SUCCEEDED,
                message=result["message"],
                result_payload=result,
            )
        return result

    try:
        created_events = extract_risk_events_for_document(document=document)
    except Exception as exc:
        result = {
            "status": "failed",
            "message": str(exc) or "风险抽取失败。",
            "created_count": 0,
            "risk_events": [],
            "document_id": document.id,
        }
        if extraction_task is not None:
            finish_risk_extraction_task(
                extraction_task,
                status=RiskExtractionTask.STATUS_FAILED,
                message=result["message"],
            )
        return result

    result = {
        "status": "succeeded",
        "message": "风险抽取完成。",
        "document_id": document.id,
        "created_count": len(created_events),
        "risk_events": RiskEventSummarySerializer(created_events, many=True).data,
    }
    if extraction_task is not None:
        finish_risk_extraction_task(
            extraction_task,
            status=RiskExtractionTask.STATUS_SUCCEEDED,
            message=result["message"],
            result_payload=result,
        )
    return result


@shared_task(name="risk.batch_extract_document_task")
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

        try:
            created_events = extract_risk_events_for_document(document=document)
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
