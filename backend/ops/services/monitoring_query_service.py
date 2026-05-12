from datetime import timedelta

from django.utils.timezone import now

from ops.models import AlertEvent, AlertRule, SystemMetric

DEFAULT_ALERT_RULE_DEFINITIONS = (
    {
        "name": "CPU 使用率过高",
        "metric_name": "cpu_percent",
        "condition": AlertRule.CONDITION_GTE,
        "threshold": 85.0,
        "severity": AlertRule.SEVERITY_CRITICAL,
        "enabled": True,
        "notification_channels": ["in_app"],
        "description": "当 CPU 使用率持续偏高时，通过站内告警提醒管理员及时排查。",
    },
    {
        "name": "内存使用率过高",
        "metric_name": "memory_percent",
        "condition": AlertRule.CONDITION_GTE,
        "threshold": 85.0,
        "severity": AlertRule.SEVERITY_WARNING,
        "enabled": True,
        "notification_channels": ["in_app"],
        "description": "用于发现内存占用持续上升或潜在泄漏。",
    },
    {
        "name": "磁盘使用率过高",
        "metric_name": "disk_percent",
        "condition": AlertRule.CONDITION_GTE,
        "threshold": 80.0,
        "severity": AlertRule.SEVERITY_CRITICAL,
        "enabled": True,
        "notification_channels": ["in_app"],
        "description": "磁盘余量不足时尽早预警，避免影响上传、解析和索引任务。",
    },
    {
        "name": "Celery Worker 不可用",
        "metric_name": "celery_worker_count",
        "condition": AlertRule.CONDITION_LT,
        "threshold": 1.0,
        "severity": AlertRule.SEVERITY_CRITICAL,
        "enabled": True,
        "notification_channels": ["in_app"],
        "description": "当异步任务执行器不可用时，提醒管理员检查队列和 worker 状态。",
    },
)


def get_current_system_status():
    metric_names = [
        "cpu_percent",
        "memory_percent",
        "disk_percent",
        "celery_worker_count",
        "db_healthy",
        "redis_healthy",
        "milvus_healthy",
    ]

    metrics = {}
    for name in metric_names:
        latest = (
            SystemMetric.objects.filter(metric_name=name)
            .order_by("-collected_at")
            .first()
        )
        if latest:
            metrics[name] = {
                "value": latest.value,
                "unit": latest.unit,
                "tags": latest.tags,
                "collected_at": latest.collected_at.isoformat(),
            }

    # Count active alerts
    firing_count = AlertEvent.objects.filter(status=AlertEvent.STATUS_FIRING).count()

    return {
        "metrics": metrics,
        "firing_alerts": firing_count,
        "collected_at": now().isoformat(),
    }


def get_metric_time_series(*, metric_name, hours=24):
    since = now() - timedelta(hours=hours)
    qs = (
        SystemMetric.objects.filter(
            metric_name=metric_name,
            collected_at__gte=since,
        )
        .order_by("collected_at")
    )

    return {
        "metric_name": metric_name,
        "hours": hours,
        "data_points": [
            {
                "value": m.value,
                "unit": m.unit,
                "collected_at": m.collected_at.isoformat(),
            }
            for m in qs
        ],
    }


def list_alert_rules(*, enabled_only=False):
    qs = AlertRule.objects.all()
    if enabled_only:
        qs = qs.filter(enabled=True)
    return [_serialize_rule(r) for r in qs]


def get_alert_rule(*, rule_id):
    try:
        rule = AlertRule.objects.get(id=rule_id)
        return _serialize_rule(rule)
    except AlertRule.DoesNotExist:
        return None


def create_alert_rule(
    *,
    name,
    metric_name,
    condition,
    threshold,
    severity="warning",
    enabled=True,
    notification_channels=None,
    description="",
    created_by=None,
):
    rule = AlertRule.objects.create(
        name=name,
        metric_name=metric_name,
        condition=condition,
        threshold=threshold,
        severity=severity,
        enabled=enabled,
        notification_channels=notification_channels or [],
        description=description,
        created_by=created_by,
    )
    return _serialize_rule(rule)


def seed_default_alert_rules(*, created_by=None):
    created = 0
    skipped = 0
    seeded_rules = []

    for definition in DEFAULT_ALERT_RULE_DEFINITIONS:
        rule, was_created = AlertRule.objects.get_or_create(
            name=definition["name"],
            defaults={
                "metric_name": definition["metric_name"],
                "condition": definition["condition"],
                "threshold": definition["threshold"],
                "severity": definition["severity"],
                "enabled": definition["enabled"],
                "notification_channels": definition["notification_channels"],
                "description": definition["description"],
                "created_by": created_by,
            },
        )
        created += int(was_created)
        skipped += int(not was_created)
        seeded_rules.append(_serialize_rule(rule))

    return {
        "created": created,
        "skipped": skipped,
        "rules": seeded_rules,
    }


def update_alert_rule(*, rule, **kwargs):
    allowed_fields = {
        "name",
        "metric_name",
        "condition",
        "threshold",
        "severity",
        "enabled",
        "notification_channels",
        "description",
    }
    for field, value in kwargs.items():
        if field in allowed_fields:
            setattr(rule, field, value)
    rule.save()
    return _serialize_rule(rule)


def delete_alert_rule(*, rule):
    rule.delete()


def list_alert_events(*, status=None, limit=50):
    qs = AlertEvent.objects.select_related("rule", "acknowledged_by")
    if status:
        qs = qs.filter(status=status)
    qs = qs[:limit]
    return [_serialize_event(e) for e in qs]


def acknowledge_event(*, event_id, user):
    event = AlertEvent.objects.get(id=event_id)
    if event.status != AlertEvent.STATUS_FIRING:
        raise ValueError("只能确认状态为 firing 的告警事件。")
    event.status = AlertEvent.STATUS_ACKNOWLEDGED
    event.acknowledged_by = user
    event.save(update_fields=["status", "acknowledged_by"])
    return _serialize_event(event)


def _serialize_rule(rule):
    return {
        "id": rule.id,
        "name": rule.name,
        "metric_name": rule.metric_name,
        "condition": rule.condition,
        "threshold": rule.threshold,
        "severity": rule.severity,
        "enabled": rule.enabled,
        "notification_channels": rule.notification_channels,
        "description": rule.description,
        "created_by": rule.created_by_id,
        "created_at": rule.created_at.isoformat() if rule.created_at else None,
        "updated_at": rule.updated_at.isoformat() if rule.updated_at else None,
    }


def _serialize_event(event):
    return {
        "id": event.id,
        "rule_id": event.rule_id,
        "rule_name": event.rule.name if event.rule else None,
        "severity": event.rule.severity if event.rule else None,
        "metric_name": event.rule.metric_name if event.rule else None,
        "condition": event.rule.condition if event.rule else None,
        "threshold": event.rule.threshold if event.rule else None,
        "notification_channels": event.rule.notification_channels if event.rule else [],
        "status": event.status,
        "triggered_value": event.triggered_value,
        "triggered_at": event.triggered_at.isoformat() if event.triggered_at else None,
        "resolved_at": event.resolved_at.isoformat() if event.resolved_at else None,
        "acknowledged_by": event.acknowledged_by_id,
        "acknowledged_by_name": (
            event.acknowledged_by.username if event.acknowledged_by else None
        ),
        "created_at": event.created_at.isoformat() if event.created_at else None,
    }
