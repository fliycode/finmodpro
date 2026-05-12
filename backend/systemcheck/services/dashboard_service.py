from datetime import timedelta

from django.db.models import Case, Count, F, IntegerField, Q, Sum, When
from django.utils import timezone

from knowledgebase.models import Document, IngestionTask
from llm.models import EvalRecord, ModelConfig, ModelInvocationLog
from rag.models import RetrievalLog
from systemcheck.models import AuditRecord
from systemcheck.services.audit_service import list_audit_records
from risk.models import RiskEvent


def _build_knowledgebase_count():
    # The current backend still exposes a single implicit knowledge base.
    return 1 if Document.objects.exists() else 0


def _format_percentage(numerator, denominator):
    if denominator <= 0:
        return "0.0%"
    return f"{(numerator / denominator) * 100:.1f}%"


def _build_daily_series(*, days, values_by_day):
    series = []
    today = timezone.localdate()
    for offset in range(days - 1, -1, -1):
        current_day = today - timedelta(days=offset)
        series.append(
            {
                "date": current_day.isoformat(),
                "value": int(values_by_day.get(current_day, 0)),
            }
        )
    return series


def _build_window_summary(*, queryset, date_field, days=7):
    today = timezone.localdate()
    current_start_day = today - timedelta(days=days - 1)
    previous_start_day = current_start_day - timedelta(days=days)

    current_filter = {f"{date_field}__date__gte": current_start_day}
    previous_filter = {
        f"{date_field}__date__gte": previous_start_day,
        f"{date_field}__date__lt": current_start_day,
    }
    series_key = f"{date_field}__date"

    current_rows = (
        queryset.filter(**current_filter)
        .values(series_key)
        .annotate(value=Count("id"))
    )
    values_by_day = {
        row[series_key]: row["value"]
        for row in current_rows
    }

    return {
        "current_count": queryset.filter(**current_filter).count(),
        "previous_count": queryset.filter(**previous_filter).count(),
        "series": _build_daily_series(days=days, values_by_day=values_by_day),
    }


def _build_value_window_summary(*, queryset, date_field, value_expression, days=7):
    today = timezone.localdate()
    current_start_day = today - timedelta(days=days - 1)
    previous_start_day = current_start_day - timedelta(days=days)

    current_filter = {f"{date_field}__date__gte": current_start_day}
    previous_filter = {
        f"{date_field}__date__gte": previous_start_day,
        f"{date_field}__date__lt": current_start_day,
    }
    series_key = f"{date_field}__date"

    current_rows = (
        queryset.filter(**current_filter)
        .values(series_key)
        .annotate(value=Sum(value_expression))
    )
    values_by_day = {
        row[series_key]: int(row["value"] or 0)
        for row in current_rows
    }

    current_total = queryset.filter(**current_filter).aggregate(total=Sum(value_expression))["total"] or 0
    previous_total = queryset.filter(**previous_filter).aggregate(total=Sum(value_expression))["total"] or 0

    return {
        "current_total": int(current_total),
        "previous_total": int(previous_total),
        "series": _build_daily_series(days=days, values_by_day=values_by_day),
    }


def _get_recent_activity(limit=8):
    items = []

    for task in IngestionTask.objects.select_related("document").order_by("-created_at", "-id")[:4]:
        tone = "risk" if task.status == IngestionTask.STATUS_FAILED else "info"
        items.append(
            {
                "type": "ingestion",
                "tone": tone,
                "status": task.status,
                "timestamp": task.created_at.isoformat(),
                "message": f"文档《{task.document.title}》入库任务状态为 {task.status}。",
            }
        )

    for event in RiskEvent.objects.order_by("-created_at", "-id")[:4]:
        tone = "risk" if event.risk_level in {RiskEvent.LEVEL_HIGH, RiskEvent.LEVEL_CRITICAL} else "warning"
        items.append(
            {
                "type": "risk",
                "tone": tone,
                "status": event.review_status,
                "timestamp": event.created_at.isoformat(),
                "message": f"{event.company_name} 产生 {event.risk_level} 风险事件，当前审核状态为 {event.review_status}。",
            }
        )

    for log in RetrievalLog.objects.order_by("-created_at", "-id")[:4]:
        tone = "info" if log.result_count > 0 else "warning"
        items.append(
            {
                "type": "retrieval",
                "tone": tone,
                "status": "hit" if log.result_count > 0 else "miss",
                "timestamp": log.created_at.isoformat(),
                "message": f"检索问题“{log.query}”返回 {log.result_count} 条结果。",
            }
        )

    for record in EvalRecord.objects.order_by("-created_at", "-id")[:4]:
        tone = "risk" if record.status == EvalRecord.STATUS_FAILED else "info"
        items.append(
            {
                "type": "evaluation",
                "tone": tone,
                "status": record.status,
                "timestamp": record.created_at.isoformat(),
                "message": f"模型评测目标 {record.target_name} 执行状态为 {record.status}。",
            }
        )

    items.sort(key=lambda item: item["timestamp"], reverse=True)
    return items[:limit]


def _get_recent_failures(limit=4):
    failures = []
    for task in IngestionTask.objects.select_related("document").filter(status=IngestionTask.STATUS_FAILED).order_by("-updated_at", "-id")[:limit]:
        failures.append(
            {
                "id": task.id,
                "document_id": task.document_id,
                "document_title": task.document.title,
                "status": task.status,
                "current_step": task.current_step,
                "retry_count": task.retry_count,
                "error_message": task.error_message or task.document.error_message or "",
                "updated_at": task.updated_at.isoformat(),
            }
        )
    return failures


def get_dashboard_stats():
    today = timezone.localdate()
    start_of_today = timezone.now() - timedelta(hours=24)
    start_day = today - timedelta(days=6)

    document_counts = Document.objects.aggregate(
        document_count=Count("id"),
        indexed_document_count=Count("id", filter=Q(status=Document.STATUS_INDEXED)),
        processing_document_count=Count(
            "id",
            filter=Q(status__in=[Document.STATUS_UPLOADED, Document.STATUS_PARSED, Document.STATUS_CHUNKED]),
        ),
        failed_document_count=Count("id", filter=Q(status=Document.STATUS_FAILED)),
    )
    risk_counts = RiskEvent.objects.aggregate(
        risk_event_count=Count("id"),
        pending_risk_event_count=Count("id", filter=Q(review_status=RiskEvent.STATUS_PENDING)),
        high_risk_event_count=Count(
            "id",
            filter=Q(risk_level__in=[RiskEvent.LEVEL_HIGH, RiskEvent.LEVEL_CRITICAL]),
        ),
    )

    active_model_count = ModelConfig.objects.filter(is_active=True).count()
    chat_request_count_24h = RetrievalLog.objects.filter(
        source=RetrievalLog.SOURCE_CHAT_ASK,
        created_at__gte=start_of_today,
    ).count()

    recent_logs = RetrievalLog.objects.filter(
        source=RetrievalLog.SOURCE_CHAT_ASK,
        created_at__date__gte=start_day,
    )
    hit_logs = recent_logs.filter(result_count__gt=0)

    model_invocation_logs = ModelInvocationLog.objects.all()
    token_total_expression = Case(
        When(total_tokens__gt=0, then=F("total_tokens")),
        default=F("request_tokens") + F("response_tokens"),
        output_field=IntegerField(),
    )
    model_invocation_summary = _build_window_summary(
        queryset=model_invocation_logs,
        date_field="created_at",
    )
    token_usage_summary = _build_value_window_summary(
        queryset=model_invocation_logs,
        date_field="created_at",
        value_expression=token_total_expression,
    )
    request_token_summary = _build_value_window_summary(
        queryset=model_invocation_logs,
        date_field="created_at",
        value_expression=F("request_tokens"),
    )
    response_token_summary = _build_value_window_summary(
        queryset=model_invocation_logs,
        date_field="created_at",
        value_expression=F("response_tokens"),
    )
    token_totals = model_invocation_logs.aggregate(
        total_token_count=Sum(token_total_expression),
        total_request_token_count=Sum("request_tokens"),
        total_response_token_count=Sum("response_tokens"),
    )
    audit_operation_summary = _build_window_summary(
        queryset=AuditRecord.objects.all(),
        date_field="created_at",
    )
    document_addition_summary = _build_window_summary(
        queryset=Document.objects.all(),
        date_field="created_at",
    )
    indexed_document_completion_summary = _build_window_summary(
        queryset=IngestionTask.objects.filter(status=IngestionTask.STATUS_SUCCEEDED),
        date_field="finished_at",
    )

    chat_requests_by_day = {
        row["created_at__date"]: row["value"]
        for row in recent_logs.values("created_at__date").annotate(value=Count("id"))
    }
    retrieval_hits_by_day = {
        row["created_at__date"]: row["value"]
        for row in hit_logs.values("created_at__date").annotate(value=Count("id"))
    }

    risk_level_distribution = {
        RiskEvent.LEVEL_LOW: 0,
        RiskEvent.LEVEL_MEDIUM: 0,
        RiskEvent.LEVEL_HIGH: 0,
        RiskEvent.LEVEL_CRITICAL: 0,
    }
    for row in RiskEvent.objects.values("risk_level").annotate(value=Count("id")):
        risk_level_distribution[row["risk_level"]] = row["value"]

    document_status_distribution = {
        Document.STATUS_UPLOADED: 0,
        Document.STATUS_PARSED: 0,
        Document.STATUS_CHUNKED: 0,
        Document.STATUS_INDEXED: 0,
        Document.STATUS_FAILED: 0,
    }
    for row in Document.objects.values("status").annotate(value=Count("id")):
        document_status_distribution[row["status"]] = row["value"]

    return {
        "knowledgebase_count": _build_knowledgebase_count(),
        "document_count": document_counts["document_count"],
        "indexed_document_count": document_counts["indexed_document_count"],
        "processing_document_count": document_counts["processing_document_count"],
        "failed_document_count": document_counts["failed_document_count"],
        "retryable_ingestion_count": IngestionTask.objects.filter(status=IngestionTask.STATUS_FAILED).count(),
        "recent_failures": _get_recent_failures(),
        "risk_event_count": risk_counts["risk_event_count"],
        "pending_risk_event_count": risk_counts["pending_risk_event_count"],
        "high_risk_event_count": risk_counts["high_risk_event_count"],
        "active_model_count": active_model_count,
        "chat_request_count_24h": chat_request_count_24h,
        "model_invocation_count_7d": model_invocation_summary["current_count"],
        "model_invocation_count_prev_7d": model_invocation_summary["previous_count"],
        "model_invocations_7d": model_invocation_summary["series"],
        "total_token_count": int(token_totals["total_token_count"] or 0),
        "total_request_token_count": int(token_totals["total_request_token_count"] or 0),
        "total_response_token_count": int(token_totals["total_response_token_count"] or 0),
        "token_count_7d": token_usage_summary["current_total"],
        "token_count_prev_7d": token_usage_summary["previous_total"],
        "token_usage_7d": token_usage_summary["series"],
        "request_tokens_7d": request_token_summary["series"],
        "response_tokens_7d": response_token_summary["series"],
        "audit_operation_count_7d": audit_operation_summary["current_count"],
        "audit_operation_count_prev_7d": audit_operation_summary["previous_count"],
        "audit_operations_7d": audit_operation_summary["series"],
        "document_added_count_7d": document_addition_summary["current_count"],
        "document_added_count_prev_7d": document_addition_summary["previous_count"],
        "indexed_document_completed_count_7d": indexed_document_completion_summary["current_count"],
        "indexed_document_completed_count_prev_7d": indexed_document_completion_summary["previous_count"],
        "retrieval_hit_rate_7d": _format_percentage(hit_logs.count(), recent_logs.count()),
        "chat_requests_7d": _build_daily_series(days=7, values_by_day=chat_requests_by_day),
        "retrieval_hits_7d": _build_daily_series(days=7, values_by_day=retrieval_hits_by_day),
        "risk_level_distribution": risk_level_distribution,
        "document_status_distribution": document_status_distribution,
        "recent_activity": _get_recent_activity(),
        "audit_snippets": list_audit_records(limit=4),
    }
