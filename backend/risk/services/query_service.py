from risk.models import RiskEvent


def build_risk_event_queryset(*, filters):
    queryset = RiskEvent.objects.select_related("document", "chunk").all()

    company_name = filters.get("company_name")
    if company_name:
        queryset = queryset.filter(company_name__icontains=company_name)

    risk_type = filters.get("risk_type")
    if risk_type:
        queryset = queryset.filter(risk_type__icontains=risk_type)

    review_status = filters.get("review_status")
    if review_status:
        queryset = queryset.filter(review_status=review_status)

    risk_level = filters.get("risk_level")
    if risk_level:
        queryset = queryset.filter(risk_level=risk_level)

    document_id = filters.get("document_id")
    if document_id:
        queryset = queryset.filter(document_id=document_id)

    period_start = filters.get("period_start")
    if period_start:
        queryset = queryset.filter(event_time__date__gte=period_start)

    period_end = filters.get("period_end")
    if period_end:
        queryset = queryset.filter(event_time__date__lte=period_end)

    return queryset


def list_risk_events(*, filters):
    return build_risk_event_queryset(filters=filters).order_by("-created_at", "-id")
