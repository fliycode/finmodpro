"""
风险分析概览服务 —— 聚合多维度风险事件统计数据。
类比 SpringBoot: 相当于 @Service 中的报表/仪表盘数据聚合层，
从 RiskEvent 表中计算出关键指标、分布、趋势和 Top 排行。
"""

from django.db.models import Count, Q
from django.db.models.functions import TruncDate

from risk.models import RiskEvent
from risk.services.query_service import build_risk_event_queryset


def _build_distribution(queryset, *, field_name):
    """
    构建指定字段的分布统计（分组计数）。

    参数:
        queryset (QuerySet): 已过滤的风险事件查询集。
        field_name (str): 分组字段名（如 risk_level, risk_type）。

    返回:
        list[dict]: [{"key": field_value, "value": count}, ...] 格式的分布数据。
    """
    return [
        {"key": row[field_name], "value": row["value"]}
        for row in queryset.values(field_name).annotate(value=Count("id")).order_by(field_name)
        if row[field_name]
    ]


def build_risk_analytics_overview(*, filters):
    """
    构建风险分析概览数据，包含关键指标、分布、趋势和 Top 排行。

    类比 SpringBoot: 相当于仪表盘 API 的后端数据聚合方法。

    参数:
        filters (dict): 与事件列表相同的过滤条件字典。

    返回:
        dict: {
            "summary": {total_events, high_risk_events, pending_reviews, unique_companies, document_count},
            "risk_level_distribution": [{key, value}, ...],
            "risk_type_distribution": [{key, value}, ...],
            "review_status_distribution": [{key, value}, ...],
            "trend": [{date, value}, ...],  # 按日统计的事件趋势
            "top_companies": [{key, value}, ...],  # Top 5 公司
        }
    """
    queryset = build_risk_event_queryset(filters=filters)

    agg = queryset.aggregate(
        total_events=Count("id"),
        high_risk_events=Count("id", filter=Q(risk_level__in=[RiskEvent.LEVEL_HIGH, RiskEvent.LEVEL_CRITICAL])),
        pending_reviews=Count("id", filter=Q(review_status=RiskEvent.STATUS_PENDING)),
        unique_companies=Count("company_name", distinct=True),
        document_count=Count("document_id", distinct=True),
    )
    summary = {
        "total_events": agg["total_events"],
        "high_risk_events": agg["high_risk_events"],
        "pending_reviews": agg["pending_reviews"],
        "unique_companies": agg["unique_companies"],
        "document_count": agg["document_count"],
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
