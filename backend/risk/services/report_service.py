import json

from django.db.models import Count

from risk.models import RiskEvent, RiskReport


def _build_risk_type_counts(*, event_ids):
    return {
        row["risk_type"]: row["count"]
        for row in RiskEvent.objects.filter(id__in=event_ids)
        .values("risk_type")
        .annotate(count=Count("id"))
        .order_by("risk_type")
    }


def _build_risk_level_counts(*, event_ids):
    return {
        row["risk_level"]: row["count"]
        for row in RiskEvent.objects.filter(id__in=event_ids)
        .values("risk_level")
        .annotate(count=Count("id"))
        .order_by("risk_level")
    }


def _collect_source_metadata(*, events):
    event_ids = [event.id for event in events]
    return {
        "event_ids": event_ids,
        "document_ids": sorted({event.document_id for event in events if event.document_id is not None}),
        "risk_type_counts": _build_risk_type_counts(event_ids=event_ids),
        "risk_level_counts": _build_risk_level_counts(event_ids=event_ids),
        "event_count": len(events),
    }


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


def _build_time_range_report_title(*, period_start, period_end):
    return f"时间区间风险报告（{period_start} 至 {period_end}）"


def _build_time_range_report_summary(*, period_start, period_end, event_count, risk_type_counts):
    ordered_types = sorted(risk_type_counts.items(), key=lambda item: (-item[1], item[0]))
    top_risk_types = "、".join(f"{risk_type}({count})" for risk_type, count in ordered_types[:3])
    return (
        f"{period_start} 至 {period_end} 共汇总 {event_count} 条已审核通过风险事件。"
        f"主要风险类型分布：{top_risk_types or '无'}。"
    )


def _build_time_range_report_content(*, title, period_start, period_end, events, risk_type_counts, risk_level_counts):
    lines = [
        title,
        "",
        f"时间区间：{period_start} 至 {period_end}",
        f"已审核通过事件数：{len(events)}",
        f"风险类型分布：{risk_type_counts}",
        f"风险等级分布：{risk_level_counts}",
        "",
        "风险事件明细：",
    ]
    for event in events:
        lines.append(
            f"- [{event.company_name}][{event.risk_type}/{event.risk_level}] {event.summary}（event_id={event.id}）"
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

    source_metadata = _collect_source_metadata(events=events)

    title = _build_company_report_title(
        company_name=company_name,
        period_start=period_start,
        period_end=period_end,
    )
    summary = _build_company_report_summary(
        company_name=company_name,
        event_count=len(events),
        risk_type_counts=source_metadata["risk_type_counts"],
    )
    content = _build_company_report_content(
        company_name=company_name,
        title=title,
        events=events,
        risk_type_counts=source_metadata["risk_type_counts"],
        risk_level_counts=source_metadata["risk_level_counts"],
    )

    report = RiskReport.objects.create(
        scope_type=RiskReport.SCOPE_COMPANY,
        title=title,
        company_name=company_name,
        period_start=period_start,
        period_end=period_end,
        summary=summary,
        content=content,
        source_metadata=source_metadata,
    )
    return report


def generate_time_range_risk_report(*, period_start, period_end):
    events = list(
        RiskEvent.objects.filter(
            review_status=RiskEvent.STATUS_APPROVED,
            event_time__date__gte=period_start,
            event_time__date__lte=period_end,
        )
        .select_related("document")
        .order_by("event_time", "id")
    )
    if not events:
        raise RiskEvent.DoesNotExist

    source_metadata = _collect_source_metadata(events=events)
    title = _build_time_range_report_title(period_start=period_start, period_end=period_end)
    summary = _build_time_range_report_summary(
        period_start=period_start,
        period_end=period_end,
        event_count=len(events),
        risk_type_counts=source_metadata["risk_type_counts"],
    )
    content = _build_time_range_report_content(
        title=title,
        period_start=period_start,
        period_end=period_end,
        events=events,
        risk_type_counts=source_metadata["risk_type_counts"],
        risk_level_counts=source_metadata["risk_level_counts"],
    )

    report = RiskReport.objects.create(
        scope_type=RiskReport.SCOPE_TIME_RANGE,
        title=title,
        period_start=period_start,
        period_end=period_end,
        summary=summary,
        content=content,
        source_metadata=source_metadata,
    )
    return report


def build_risk_report_export(*, report, export_format="markdown"):
    if export_format == "markdown":
        lines = [
            f"# {report.title}",
            "",
            f"- 报告范围: {report.scope_type}",
            f"- 生成时间: {report.created_at.isoformat()}",
        ]
        if report.company_name:
            lines.append(f"- 公司: {report.company_name}")
        if report.period_start or report.period_end:
            lines.append(f"- 时间区间: {report.period_start or '-'} 至 {report.period_end or '-'}")
        lines.extend(
            [
                "",
                "## 摘要",
                report.summary or "暂无摘要",
                "",
                "## 报告内容",
                report.content,
                "",
                "## 源数据",
                json.dumps(report.source_metadata or {}, ensure_ascii=False, indent=2),
                "",
            ]
        )
        return {
            "filename": f"risk-report-{report.id}.md",
            "content_type": "text/markdown",
            "content": "\n".join(lines),
        }

    if export_format == "json":
        payload = {
            "id": report.id,
            "scope_type": report.scope_type,
            "title": report.title,
            "company_name": report.company_name,
            "period_start": report.period_start.isoformat() if report.period_start else None,
            "period_end": report.period_end.isoformat() if report.period_end else None,
            "summary": report.summary,
            "content": report.content,
            "source_metadata": report.source_metadata,
            "created_at": report.created_at.isoformat(),
            "updated_at": report.updated_at.isoformat(),
        }
        return {
            "filename": f"risk-report-{report.id}.json",
            "content_type": "application/json",
            "content": json.dumps(payload, ensure_ascii=False, indent=2),
        }

    raise ValueError("仅支持 markdown 或 json 导出格式。")
