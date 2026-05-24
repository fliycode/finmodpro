"""
风险提取服务 —— 从文档中提取风险事件的完整业务流程。
类比 SpringBoot: 相当于 @Service 中的核心业务编排层，
协调切块筛选、LLM 抽取-验证循环、判读增强、去重去重和持久化。

主要流程:
1. 筛选风险相关切块 (chunk_filter_service)
2. 限制内容长度 (limit_extraction_chunks)
3. 多轮提取-验证循环 (verification_service)
4. 判读增强 (adjudication_service)
5. 去重过滤 (防重复检测)
6. 持久化到数据库
"""

from django.conf import settings
from django.db import models, transaction

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


def _text_bigrams(text):
    """
    将文本拆分为 bigram（双字符组）集合，用于相似度计算。

    参数:
        text (str): 输入文本。

    返回:
        set: bigram 集合。
    """
    text = str(text or "").strip()
    return set(text[i:i + 2] for i in range(len(text) - 1)) if len(text) >= 2 else {text}


def _text_similarity(text_a, text_b):
    """
    使用 Jaccard 相似度（基于 bigram）计算两段文本的相似度。

    参数:
        text_a (str): 文本 A。
        text_b (str): 文本 B。

    返回:
        float: [0.0, 1.0] 的相似度分数。
    """
    if not text_a or not text_b:
        return 0.0
    bg_a = _text_bigrams(text_a)
    bg_b = _text_bigrams(text_b)
    if not bg_a or not bg_b:
        return 0.0
    intersection = len(bg_a & bg_b)
    union = len(bg_a | bg_b)
    return intersection / union if union > 0 else 0.0


def _filter_against_existing(*, document, extracted_events):
    """
    将新提取的事件与数据库中已有事件进行相似度比较，过滤掉重复事件。

    参数:
        document (Document): 文档实例。
        extracted_events (list[dict]): 新提取的风险事件列表。

    返回:
        list[dict]: 去重后的事件列表。
    """
    existing_events = list(
        RiskEvent.objects.filter(document=document).values(
            "company_name", "risk_type", "summary", "evidence_text"
        )
    )
    if not existing_events:
        return extracted_events

    threshold = getattr(settings, "RISK_EXTRACTION_MERGE_SIMILARITY_THRESHOLD", 0.35)
    new_events = []
    for event in extracted_events:
        is_duplicate = False
        new_text = str(event.get("summary", "")) + str(event.get("evidence_text", ""))
        for existing in existing_events:
            if event.get("risk_type") != existing.get("risk_type"):
                continue
            existing_text = str(existing.get("summary", "")) + str(existing.get("evidence_text", ""))
            if _text_similarity(new_text, existing_text) >= threshold:
                is_duplicate = True
                break
        if not is_duplicate:
            new_events.append(event)
    return new_events


# 风险信号关键词列表，用于快速检测文档是否含有潜在风险内容
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
    """
    获取文档的所有 chunk，按 chunk_index 排序。

    参数:
        document (Document): 文档实例。

    返回:
        list[DocumentChunk]: chunk 列表。
    """
    return list(DocumentChunk.objects.filter(document=document).order_by("chunk_index", "id"))


def _build_chunk_context(chunks):
    """
    将 chunk 列表拼接为 LLM 可读的上下文字符串。

    参数:
        chunks (list[DocumentChunk]): chunk 列表。

    返回:
        str: 形如 "[chunk_id=x][chunk_index=y] content..." 的拼接文本。
    """
    return "\n\n".join(
        f"[chunk_id={chunk.id}][chunk_index={chunk.chunk_index}] {chunk.content}" for chunk in chunks
    )


def _resolve_chunk(*, raw_chunk_id, chunk_by_id):
    """
    根据 LLM 输出的 chunk_id 解析出对应的 DocumentChunk 实例。

    参数:
        raw_chunk_id: LLM 输出的原始 chunk_id。
        chunk_by_id (dict): {chunk_id: DocumentChunk} 的映射。

    返回:
        DocumentChunk | None: 对应的 chunk 实例，找不到时返回 None。
    """
    if raw_chunk_id is None:
        return None
    try:
        return chunk_by_id[int(raw_chunk_id)]
    except (KeyError, TypeError, ValueError):
        return None


def limit_extraction_chunks(*, chunks, max_chunks=None, max_chars=None):
    """
    限制传入 LLM 的 chunk 数量和总字符数，避免超出 token 限制。

    参数:
        chunks (list[DocumentChunk]): 待限制的 chunk 列表。
        max_chunks (int, 可选): 最大 chunk 数量。
        max_chars (int, 可选): 最大字符数。

    返回:
        list[DocumentChunk]: 截断后的 chunk 列表，至少保留第一个。
    """
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
    """
    快速检测文档是否包含风险信号关键词。

    参数:
        document (Document): 文档实例。
        chunks (list[DocumentChunk]): 前 24 个 chunk。

    返回:
        dict: {"has_signal": bool, "matched_keywords": list[str]}。
    """
    text_parts = [document.title or ""]
    text_parts.extend(chunk.content or "" for chunk in chunks[:24])
    corpus = "\n".join(text_parts).lower()

    matched_keywords = [keyword for keyword in RISK_SIGNAL_KEYWORDS if keyword.lower() in corpus]
    return {
        "has_signal": bool(matched_keywords),
        "matched_keywords": matched_keywords[:8],
    }


def extract_risk_events_for_document(*, document, stage_callback=None):
    """
    从单个文档中提取风险事件的完整流程。

    类比 SpringBoot: 相当于 @Service 中的核心业务流程方法。
    流程: chunk 列表 -> 筛选 -> 限制长度 -> 抽取+验证 -> 判读 -> 去重 -> 持久化。

    参数:
        document (Document): 要分析的文档实例。
        stage_callback (callable, 可选): 阶段进度回调，签名:
            callback(step=str, progress=int, message=str)

    返回:
        list[RiskEvent]: 新创建的风险事件实例列表。
    """
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
        extracted_events = _filter_against_existing(
            document=document,
            extracted_events=extracted_events,
        )
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
    """
    批量从多个文档中提取风险事件。

    参数:
        document_ids (list[int]): 文档 ID 列表。

    返回:
        dict: {
            "total_documents": int,
            "processed_documents": int,
            "total_created_count": int,
            "results": [{document_id, status, message, created_count, risk_events}, ...],
        }
    """
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
