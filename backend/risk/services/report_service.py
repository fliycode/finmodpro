from django.db.models import Count

from risk.models import RiskEvent, RiskReport


def _build_company_report_title(*, company_name, period_start=None, period_end=None):
    if period_start and period_end:
        return f"{company_name} 风险报告（{period_start} 至 {period_end}）"
    return f"{company_name} 风险报告"


def _build_company_report_summary(*, company_name, event_count, risk_type_counts):
    ordered_types = sorted(risk_type_counts.items(), key=lambda item: (-item[1], item[0]))
    top_risk_types = "、".join(f"{risk_type}({count})" for risk_type, count in ordered_types[:3])
    return (
        f"{company_name} 共汇总 {event_count} 条已审核通过风险事件。"
        f"主要风险类型分布：{top_risk_types or '无'}。"
    )


def _build_company_report_content(*, company_name, title, events, risk_type_counts, risk_level_counts):
    lines = [
        title,
        "",
        f"公司：{company_name}",
        f"已审核通过事件数：{len(events)}",
        f"风险类型分布：{risk_type_counts}",
        f"风险等级分布：{risk_level_counts}",
        "",
        "风险事件明细：",
    ]
    for event in events:
        lines.append(
            f"- [{event.risk_type}/{event.risk_level}] {event.summary}（event_id={event.id}）"
        )
    return "\n".join(lines)


def generate_company_risk_report(*, company_name, period_start=None, period_end=None):
    events = RiskEvent.objects.filter(
        company_name=company_name,
        review_status=RiskEvent.STATUS_APPROVED,
    ).select_related("document")
    if period_start:
        events = events.filter(event_time__date__gte=period_start)
    if period_end:
        events = events.filter(event_time__date__lte=period_end)

    events = list(events.order_by("event_time", "id"))
    if not events:
        raise RiskEvent.DoesNotExist

    risk_type_counts = {
        row["risk_type"]: row["count"]
        for row in RiskEvent.objects.filter(id__in=[event.id for event in events])
        .values("risk_type")
        .annotate(count=Count("id"))
        .order_by("risk_type")
    }
    risk_level_counts = {
        row["risk_level"]: row["count"]
        for row in RiskEvent.objects.filter(id__in=[event.id for event in events])
        .values("risk_level")
        .annotate(count=Count("id"))
        .order_by("risk_level")
    }
    document_ids = sorted({event.document_id for event in events if event.document_id is not None})
    event_ids = [event.id for event in events]

    title = _build_company_report_title(
        company_name=company_name,
        period_start=period_start,
        period_end=period_end,
    )
    summary = _build_company_report_summary(
        company_name=company_name,
        event_count=len(events),
        risk_type_counts=risk_type_counts,
    )
    content = _build_company_report_content(
        company_name=company_name,
        title=title,
        events=events,
        risk_type_counts=risk_type_counts,
        risk_level_counts=risk_level_counts,
    )

    report = RiskReport.objects.create(
        scope_type=RiskReport.SCOPE_COMPANY,
        title=title,
        company_name=company_name,
        period_start=period_start,
        period_end=period_end,
        summary=summary,
        content=content,
        source_metadata={
            "event_ids": event_ids,
            "document_ids": document_ids,
            "risk_type_counts": risk_type_counts,
            "risk_level_counts": risk_level_counts,
            "event_count": len(events),
        },
    )
    return report
