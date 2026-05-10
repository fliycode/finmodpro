import logging
from datetime import timezone as tz

from django.utils.timezone import now

logger = __import__("logging").getLogger(__name__)


def evaluate_alert_rules():
    from ops.models import AlertEvent, AlertRule, SystemMetric

    rules = list(AlertRule.objects.filter(enabled=True))
    if not rules:
        return {"evaluated": 0, "triggered": 0, "resolved": 0}

    # Group rules by metric_name for efficient lookup
    metric_names = {r.metric_name for r in rules}
    latest_metrics = {}
    for name in metric_names:
        metric = (
            SystemMetric.objects.filter(metric_name=name)
            .order_by("-collected_at")
            .first()
        )
        if metric:
            latest_metrics[name] = metric

    triggered = 0
    resolved = 0

    for rule in rules:
        metric = latest_metrics.get(rule.metric_name)
        if metric is None:
            continue

        is_violated = _compare_value(
            value=metric.value,
            condition=rule.condition,
            threshold=rule.threshold,
        )

        if is_violated:
            # Check if there's already a firing event for this rule
            existing_firing = AlertEvent.objects.filter(
                rule=rule,
                status=AlertEvent.STATUS_FIRING,
            ).first()

            if existing_firing is None:
                AlertEvent.objects.create(
                    rule=rule,
                    status=AlertEvent.STATUS_FIRING,
                    triggered_value=metric.value,
                    triggered_at=now(),
                )
                triggered += 1
            else:
                # Update triggered value
                existing_firing.triggered_value = metric.value
                existing_firing.save(update_fields=["triggered_value"])
        else:
            # Resolve any open firing events for this rule
            open_events = AlertEvent.objects.filter(
                rule=rule,
                status=AlertEvent.STATUS_FIRING,
            )
            count = open_events.update(
                status=AlertEvent.STATUS_RESOLVED,
                resolved_at=now(),
            )
            resolved += count

    return {
        "evaluated": len(rules),
        "triggered": triggered,
        "resolved": resolved,
    }


def acknowledge_alert_event(*, event_id, user):
    from ops.models import AlertEvent

    event = AlertEvent.objects.get(id=event_id)
    if event.status != AlertEvent.STATUS_FIRING:
        raise ValueError("只能确认状态为 firing 的告警事件。")

    event.status = AlertEvent.STATUS_ACKNOWLEDGED
    event.acknowledged_by = user
    event.save(update_fields=["status", "acknowledged_by"])
    return _serialize_alert_event(event)


def _compare_value(*, value, condition, threshold):
    if condition == "gt":
        return value > threshold
    elif condition == "lt":
        return value < threshold
    elif condition == "gte":
        return value >= threshold
    elif condition == "lte":
        return value <= threshold
    elif condition == "eq":
        return value == threshold
    return False


def _serialize_alert_event(event):
    return {
        "id": event.id,
        "rule_id": event.rule_id,
        "rule_name": event.rule.name if event.rule else None,
        "severity": event.rule.severity if event.rule else None,
        "status": event.status,
        "triggered_value": event.triggered_value,
        "triggered_at": event.triggered_at.isoformat() if event.triggered_at else None,
        "resolved_at": event.resolved_at.isoformat() if event.resolved_at else None,
        "acknowledged_by": event.acknowledged_by_id,
        "created_at": event.created_at.isoformat() if event.created_at else None,
    }
