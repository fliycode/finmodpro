from knowledgebase.models import Document
from risk.models import RiskEvent


def get_dashboard_stats():
    # The current backend exposes a single implicit knowledge base until
    # a dedicated KnowledgeBase model lands. Reflect that deployment shape
    # without hardcoding a permanent schema assumption into the controller.
    knowledgebase_count = 1 if Document.objects.exists() else 0

    return {
        "knowledgebase_count": knowledgebase_count,
        "document_count": Document.objects.count(),
        "risk_event_count": RiskEvent.objects.count(),
        "pending_risk_event_count": RiskEvent.objects.filter(
            review_status=RiskEvent.STATUS_PENDING,
        ).count(),
    }
