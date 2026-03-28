from django.db import transaction

from common.exceptions import UpstreamServiceError
from knowledgebase.models import Document
from knowledgebase.models import DocumentChunk
from llm.services.prompt_service import render_prompt
from llm.services.runtime_service import get_chat_provider
from risk.models import RiskEvent
from risk.serializers import RiskEventSummarySerializer, parse_risk_extraction_payload


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


def _parse_provider_output(raw_content):
    try:
        return parse_risk_extraction_payload(raw_content)
    except Exception as exc:
        raise UpstreamServiceError(
            "风险抽取结果格式非法。",
            status_code=502,
            code="risk_extraction_invalid_output",
        ) from exc


def extract_risk_events_for_document(*, document):
    chunks = list_document_chunks(document=document)
    if not chunks:
        return []

    provider = get_chat_provider()
    prompt = render_prompt(
        "risk/extract.txt",
        document_title=document.title,
        document_type=document.doc_type,
        chunk_context=_build_chunk_context(chunks),
    )
    raw_content = provider.chat(
        messages=[
            {
                "role": "system",
                "content": "你是金融风险抽取助手。严格输出 JSON，不要输出 markdown 或额外解释。",
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        options={"temperature": 0},
    )
    extracted_events = _parse_provider_output(raw_content)
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
                    },
                )
            )

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
