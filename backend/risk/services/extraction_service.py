from django.db import transaction

from common.exceptions import UpstreamServiceError
from common.observability import trace_span
from knowledgebase.models import Document
from knowledgebase.models import DocumentChunk
from risk.models import RiskEvent
from risk.serializers import RiskEventSummarySerializer
from risk.services.chunk_filter_service import select_risk_relevant_chunks
from risk.services.verification_service import run_extraction_with_verification


def list_document_chunks(*, document):
    return list(DocumentChunk.objects.filter(document=document).order_by("chunk_index", "id"))


def _build_chunk_context(chunks):
    return "\n\n".join(
        f"[chunk_id={chunk.id}][chunk_index={chunk.chunk_index}] {chunk.content}" for chunk in chunks
    )


def _resolve_chunk(*, raw_chunk_id, chunk_by_id):
    if raw_chunk_id is None:
        return None
    try:
        return chunk_by_id[int(raw_chunk_id)]
    except (KeyError, TypeError, ValueError):
        return None


def extract_risk_events_for_document(*, document):
    chunks = list_document_chunks(document=document)
    if not chunks:
        return []

    with trace_span(
        "risk.extract",
        metadata={"document_id": document.id, "chunk_count": len(chunks)},
        input_data={"document_title": document.title},
    ) as observation:
        filtered_chunks = select_risk_relevant_chunks(
            document=document,
            all_chunks=chunks,
        )

        extracted_events, pipeline_meta = run_extraction_with_verification(
            document=document,
            chunks=filtered_chunks,
        )

        chunk_by_id = {chunk.id: chunk for chunk in chunks}
        created_events = []
        with transaction.atomic():
            for event_data in extracted_events:
                chunk = _resolve_chunk(
                    raw_chunk_id=event_data.get("chunk_id"),
                    chunk_by_id=chunk_by_id,
                )
                created_events.append(
                    RiskEvent.objects.create(
                        company_name=event_data["company_name"],
                        risk_type=event_data["risk_type"],
                        risk_level=event_data["risk_level"],
                        event_time=event_data.get("event_time"),
                        summary=event_data["summary"],
                        evidence_text=event_data["evidence_text"],
                        confidence_score=event_data["confidence_score"],
                        review_status=RiskEvent.STATUS_PENDING,
                        document=document,
                        chunk=chunk,
                        metadata={
                            "source_document_id": document.id,
                            "source_chunk_id": event_data.get("chunk_id"),
                            "extraction_pipeline": {
                                "rounds_completed": pipeline_meta["rounds_completed"],
                                "verification_passed": pipeline_meta["verification_passed"],
                                "total_llm_calls": pipeline_meta["total_llm_calls"],
                                "chunk_filter": {
                                    "total_chunks": len(chunks),
                                    "filtered_chunks": len(filtered_chunks),
                                },
                            },
                        },
                    )
                )

        observation.update(output={
            "created_count": len(created_events),
            "rounds_completed": pipeline_meta["rounds_completed"],
            "verification_passed": pipeline_meta["verification_passed"],
            "total_llm_calls": pipeline_meta["total_llm_calls"],
        })
        return created_events


def batch_extract_risk_events_for_documents(*, document_ids):
    normalized_document_ids = list(dict.fromkeys(document_ids))
    documents_by_id = {
        document.id: document for document in Document.objects.filter(id__in=normalized_document_ids)
    }

    results = []
    total_created_count = 0
    for document_id in normalized_document_ids:
        document = documents_by_id.get(document_id)
        if document is None:
            results.append(
                {
                    "document_id": document_id,
                    "status": "not_found",
                    "message": "文档不存在。",
                    "created_count": 0,
                    "risk_events": [],
                }
            )
            continue

        chunks = list_document_chunks(document=document)
        if not chunks:
            results.append(
                {
                    "document_id": document.id,
                    "status": "no_chunks",
                    "message": "文档暂无可抽取内容。",
                    "created_count": 0,
                    "risk_events": [],
                }
            )
            continue

        try:
            created_events = extract_risk_events_for_document(document=document)
        except UpstreamServiceError as exc:
            result = {
                "document_id": document.id,
                "status": "failed",
                "message": exc.message,
                "created_count": 0,
                "risk_events": [],
                "error_code": exc.code,
            }
            if exc.provider:
                result["provider"] = exc.provider
            results.append(result)
            continue

        total_created_count += len(created_events)
        results.append(
            {
                "document_id": document.id,
                "status": "created" if created_events else "completed",
                "message": "风险抽取完成。" if created_events else "未识别到风险事件。",
                "created_count": len(created_events),
                "risk_events": RiskEventSummarySerializer(created_events, many=True).data,
            }
        )

    return {
        "total_documents": len(normalized_document_ids),
        "processed_documents": len(results),
        "total_created_count": total_created_count,
        "results": results,
    }
