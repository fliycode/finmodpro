from django.db.models import Count, Q
from django.db.models.functions import TruncDate

from risk.models import RiskEvent
from risk.services.query_service import build_risk_event_queryset


def _build_distribution(queryset, *, field_name):
    return [
        {"key": row[field_name], "value": row["value"]}
        for row in queryset.values(field_name).annotate(value=Count("id")).order_by(field_name)
        if row[field_name]
    ]


def build_risk_analytics_overview(*, filters):
    queryset = build_risk_event_queryset(filters=filters)

    total_events = queryset.count()
    summary = {
        "total_events": total_events,
        "high_risk_events": queryset.filter(
            Q(risk_level=RiskEvent.LEVEL_HIGH) | Q(risk_level=RiskEvent.LEVEL_CRITICAL)
        ).count(),
        "pending_reviews": queryset.filter(review_status=RiskEvent.STATUS_PENDING).count(),
        "unique_companies": queryset.values("company_name").distinct().count(),
        "document_count": queryset.exclude(document_id__isnull=True).values("document_id").distinct().count(),
    }

    trend = [
        {"date": row["date"].isoformat(), "value": row["value"]}
        for row in queryset.exclude(event_time__isnull=True)
        .annotate(date=TruncDate("event_time"))
        .values("date")
        .annotate(value=Count("id"))
        .order_by("date")
        if row["date"] is not None
    ]

    top_companies = [
        {"key": row["company_name"], "value": row["value"]}
        for row in queryset.values("company_name")
        .annotate(value=Count("id"))
        .order_by("-value", "company_name")[:5]
        if row["company_name"]
    ]

    return {
        "summary": summary,
        "risk_level_distribution": _build_distribution(queryset, field_name="risk_level"),
        "risk_type_distribution": _build_distribution(queryset, field_name="risk_type"),
        "review_status_distribution": _build_distribution(queryset, field_name="review_status"),
        "trend": trend,
        "top_companies": top_companies,
    }
