"""
风险分析的 Celery 异步任务定义。

类比 SpringBoot: 相当于 @Async 注解的异步方法或 Spring Batch 的 Job，
由 Celery Worker 守护进程执行。这些任务负责将 LLM 调用等耗时操作
从 HTTP 请求-响应循环中剥离，避免阻塞 Web 服务线程。

任务列表:
- extract_document_task:          单文档风险抽取（信号检测 + 抽取 + 验证 + 持久化）
- batch_extract_document_task:    批量文档风险抽取（遍历多个文档执行抽取）
- expire_stale_extractions_task:  过期任务清理（定时将僵尸任务标记为失败）
"""
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
    """
    根据任务 UUID 查找对应的 RiskExtractionTask 记录。

    参数:
        extraction_task_id (UUID | None): 任务主键。

    返回:
        RiskExtractionTask | None: 找到的任务实例，不存在时返回 None。
    """
    if extraction_task_id is None:
        return None
    try:
        return RiskExtractionTask.objects.get(id=extraction_task_id)
    except RiskExtractionTask.DoesNotExist:
        return None


def _finalize_success(extraction_task, result):
    """
    将提取任务标记为成功完成。

    参数:
        extraction_task (RiskExtractionTask | None): 任务实例，None 时跳过。
        result (dict): 提取结果数据。
    """
    if extraction_task is None:
        return
    finish_risk_extraction_task(
        extraction_task,
        status=RiskExtractionTask.STATUS_SUCCEEDED,
        message=result["message"],
        result_payload=result,
    )


def _finalize_failure(extraction_task, *, message, error_code):
    """
    将提取任务标记为失败。

    参数:
        extraction_task (RiskExtractionTask | None): 任务实例，None 时跳过。
        message (str): 失败原因描述。
        error_code (str): 错误代码（用于 HTTP 状态码映射）。
    """
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
    """
    单文档风险抽取异步任务。

    类比 SpringBoot: 相当于 @Async 方法 + Spring Batch Step 的组合。
    工作流程:
    1. 检查文档是否存在
    2. 获取文档的所有 chunk
    3. 快速检测风险关键词信号（无信号则跳过）
    4. 调用 extract_risk_events_for_document 执行完整的抽取+验证+持久化管道
    5. 超时异常和通用异常的捕获处理

    参数:
        document_id (int): 要分析的文档 ID。
        extraction_task_id (UUID, 可选): 关联的状态跟踪任务 ID。

    返回:
        dict: {status, message, document_id, created_count, risk_events, [error_code]}
              status: "not_found" | "no_chunks" | "no_signals" | "succeeded" | "failed"
    """
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
    """
    批量文档风险抽取异步任务。

    类比 SpringBoot: 相当于 @Async 批处理方法，逐个文档执行抽取。
    使用 dict.fromkeys 去重，对每个文档执行信号检测 -> 抽取的完整流程。

    参数:
        document_ids (list[int]): 要批量分析的文档 ID 列表。

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
    """
    清理过期的风险提取任务（定时任务）。

    类比 SpringBoot: 相当于 @Scheduled 的定期清理方法。
    将长时间未更新的 queued/running 任务标记为 failed。

    返回:
        dict: {"expired_count": int} 被标记为过期的任务数量。
    """
    expired_count = expire_stale_risk_extractions()
    return {"expired_count": expired_count}
