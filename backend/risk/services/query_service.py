from risk.models import RiskEvent


def list_risk_events(*, filters):
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

    return queryset.order_by("-created_at", "-id")
