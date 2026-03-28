from risk.models import RiskEvent


def review_risk_event(*, risk_event, review_status):
    risk_event.review_status = review_status
    risk_event.save(update_fields=["review_status", "updated_at"])
    return risk_event
