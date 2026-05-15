from django.conf import settings
from django.db import transaction

from common.exceptions import UpstreamServiceError
from common.observability import trace_span
from knowledgebase.models import Document
from knowledgebase.models import DocumentChunk
from risk.models import RiskEvent
from risk.models import RiskExtractionTask
from risk.serializers import RiskEventSummarySerializer
from risk.services.adjudication_service import build_event_enrichment
from risk.services.chunk_filter_service import select_risk_relevant_chunks
from risk.services.verification_service import run_extraction_with_verification

RISK_SIGNAL_KEYWORDS = (
    "风险",
    "金融",
    "流动性",
    "信用",
    "市场",
    "合规",
    "违约",
    "债务",
    "现金流",
    "兑付",
    "监管",
    "罚款",
    "诉讼",
    "破产",
    "融资",
    "亏损",
    "risk",
    "liquidity",
    "credit",
    "market",
    "compliance",
    "default",
    "debt",
    "cash flow",
    "lawsuit",
    "penalty",
    "bankruptcy",
    "financing",
)


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


def limit_extraction_chunks(*, chunks, max_chunks=None, max_chars=None):
    if not chunks:
        return []

    resolved_max_chunks = max_chunks
    if resolved_max_chunks is None:
        resolved_max_chunks = getattr(settings, "RISK_EXTRACTION_CONTEXT_MAX_CHUNKS", 8)
    resolved_max_chars = max_chars
    if resolved_max_chars is None:
        resolved_max_chars = getattr(settings, "RISK_EXTRACTION_CONTEXT_MAX_CHARS", 6000)

    limited = []
    consumed_chars = 0

    for chunk in chunks:
        if resolved_max_chunks and len(limited) >= resolved_max_chunks:
            break

        chunk_length = len(chunk.content or "")
        next_total = consumed_chars + chunk_length
        if limited and resolved_max_chars and next_total > resolved_max_chars:
            break

        limited.append(chunk)
        consumed_chars = next_total

        if resolved_max_chars and consumed_chars >= resolved_max_chars:
            break

    return limited or [chunks[0]]


def detect_risk_signals(*, document, chunks):
    text_parts = [document.title or ""]
    text_parts.extend(chunk.content or "" for chunk in chunks[:24])
    corpus = "\n".join(text_parts).lower()

    matched_keywords = [keyword for keyword in RISK_SIGNAL_KEYWORDS if keyword.lower() in corpus]
    return {
        "has_signal": bool(matched_keywords),
        "matched_keywords": matched_keywords[:8],
    }


def extract_risk_events_for_document(*, document, stage_callback=None):
    chunks = list_document_chunks(document=document)
    if not chunks:
        return []

    with trace_span(
        "risk.extract",
        metadata={"document_id": document.id, "chunk_count": len(chunks)},
        input_data={"document_title": document.title},
    ) as observation:
        if callable(stage_callback):
            stage_callback(
                step=RiskExtractionTask.STEP_RETRIEVING,
                progress=28,
                message="正在检索风险相关切块。",
            )
        filtered_chunks = select_risk_relevant_chunks(
            document=document,
            all_chunks=chunks,
        )
        extraction_chunks = limit_extraction_chunks(chunks=filtered_chunks)

        if callable(stage_callback):
            stage_callback(
                step=RiskExtractionTask.STEP_EXTRACTING,
                progress=62,
                message="正在调用模型抽取风险事件。",
            )
        extracted_events, pipeline_meta = run_extraction_with_verification(
            document=document,
            chunks=extraction_chunks,
            on_stage_update=stage_callback,
        )

        if callable(stage_callback):
            stage_callback(
                step=RiskExtractionTask.STEP_ROUTING_REVIEW,
                progress=90,
                message="正在分流需人工复核的风险事件。",
            )
        if callable(stage_callback):
            stage_callback(
                step=RiskExtractionTask.STEP_PERSISTING,
                progress=94,
                message="正在写入风险事件结果。",
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
                            **build_event_enrichment(event_data=event_data, chunk=chunk),
                            "extraction_pipeline": {
                                "rounds_completed": pipeline_meta["rounds_completed"],
                                "verification_passed": pipeline_meta["verification_passed"],
                                "total_llm_calls": pipeline_meta["total_llm_calls"],
                                "human_review_count": pipeline_meta.get("human_review_count", 0),
                                "schema_version": pipeline_meta.get("schema_version", "v2-foundation"),
                                "chunk_filter": {
                                    "total_chunks": len(chunks),
                                    "filtered_chunks": len(filtered_chunks),
                                    "used_chunks": len(extraction_chunks),
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
            "used_chunks": len(extraction_chunks),
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
