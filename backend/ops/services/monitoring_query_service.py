"""
监控查询服务 —— 提供系统状态查询、指标时序查询、告警规则/事件的完整 CRUD。
类比 SpringBoot: 相当于 @Service 中的查询层，
聚合 SystemMetric / AlertRule / AlertEvent 的数据访问，
为 Controller 层提供简洁的业务方法。
"""

from datetime import timedelta

from django.utils.timezone import now

from ops.models import AlertEvent, AlertRule, SystemMetric

# 预定义的默认告警规则模板，通过 seed_default_alert_rules 播种
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
    """
    获取当前系统状态概览，包含所有关键指标的最新值和当前活跃告警数。

    类比 SpringBoot: 相当于 Actuator /health 端点的数据聚合。

    返回:
        dict: {
            "metrics": {metric_name: {value, unit, tags, collected_at}, ...},
            "firing_alerts": int,  当前触发中的告警数,
            "collected_at": str,   查询时间戳,
        }
    """
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

    # 统计当前活跃告警数（仅 firing 状态）
    firing_count = AlertEvent.objects.filter(status=AlertEvent.STATUS_FIRING).count()

    return {
        "metrics": metrics,
        "firing_alerts": firing_count,
        "collected_at": now().isoformat(),
    }


def get_metric_time_series(*, metric_name, hours=24):
    """
    获取指定指标在指定时间范围内的历史数据点（时序数据）。

    类比 SpringBoot: 相当于 Prometheus /api/v1/query_range 的数据层实现。

    参数:
        metric_name (str): 指标名称，如 "cpu_percent"。
        hours (int, 可选): 向前查询的小时数，默认 24 小时。

    返回:
        dict: {
            "metric_name": str,
            "hours": int,
            "data_points": [{value, unit, collected_at}, ...],
        }
    """
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
    """
    获取告警规则列表。

    参数:
        enabled_only (bool, 可选): 是否仅返回启用的规则。

    返回:
        list[dict]: 序列化后的告警规则列表。
    """
    qs = AlertRule.objects.all()
    if enabled_only:
        qs = qs.filter(enabled=True)
    return [_serialize_rule(r) for r in qs]


def get_alert_rule(*, rule_id):
    """
    获取单条告警规则的详情。

    参数:
        rule_id (int): 告警规则 ID。

    返回:
        dict | None: 规则详情，不存在时返回 None。
    """
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
    """
    创建一条新的告警规则。

    类比 SpringBoot: 相当于 @Service 中的 save 方法。

    参数:
        name (str):               规则名称，必须唯一。
        metric_name (str):        要监控的指标名称。
        condition (str):          比较条件（gt / lt / gte / lte / eq）。
        threshold (float):        告警阈值。
        severity (str, 可选):     严重级别，默认 "warning"。
        enabled (bool, 可选):     是否启用，默认 True。
        notification_channels (list, 可选): 通知渠道列表。
        description (str, 可选):  规则描述。
        created_by (User, 可选):  创建者。

    返回:
        dict: 序列化后的新规则数据。
    """
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
    """
    播种预定义的默认告警规则。

    使用 get_or_create 确保幂等性 —— 已存在的规则不会被覆盖。

    参数:
        created_by (User, 可选): 创建者。

    返回:
        dict: {
            "created": int,   新创建的规则数,
            "skipped": int,   已跳过（已存在）的规则数,
            "rules": list,    所有规则（含新建和已有）的序列化数据,
        }
    """
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
    """
    部分更新告警规则 —— 仅更新提供的字段。

    参数:
        rule (AlertRule): 要更新的规则模型实例。
        **kwargs: 要更新的字段键值对，仅允许白名单中的字段。

    返回:
        dict: 更新后的规则序列化数据。
    """
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
    """
    删除一条告警规则。

    参数:
        rule (AlertRule): 要删除的规则模型实例。
    """
    rule.delete()


def list_alert_events(*, status=None, limit=50):
    """
    获取告警事件列表，支持按状态过滤。

    参数:
        status (str, 可选): 过滤状态（firing / resolved / acknowledged）。
        limit (int, 可选):  返回的最大事件数量，默认 50。

    返回:
        list[dict]: 序列化后的告警事件列表。
    """
    qs = AlertEvent.objects.select_related("rule", "acknowledged_by")
    if status:
        qs = qs.filter(status=status)
    qs = qs[:limit]
    return [_serialize_event(e) for e in qs]


def acknowledge_event(*, event_id, user):
    """
    确认一条告警事件（firing -> acknowledged）。

    参数:
        event_id (int): 告警事件 ID。
        user: 执行确认操作的用户。

    返回:
        dict: 确认后的告警事件序列化数据。

    抛出:
        ValueError: 事件状态不是 firing 时抛出。
    """
    event = AlertEvent.objects.get(id=event_id)
    if event.status != AlertEvent.STATUS_FIRING:
        raise ValueError("只能确认状态为 firing 的告警事件。")
    event.status = AlertEvent.STATUS_ACKNOWLEDGED
    event.acknowledged_by = user
    event.save(update_fields=["status", "acknowledged_by"])
    return _serialize_event(event)


def _serialize_rule(rule):
    """
    将 AlertRule 模型实例序列化为前端可用的字典。

    参数:
        rule (AlertRule): 告警规则实例。

    返回:
        dict: 序列化后的规则数据。
    """
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
    """
    将 AlertEvent 模型实例序列化为前端可用的字典。

    参数:
        event (AlertEvent): 告警事件实例。

    返回:
        dict: 序列化后的事件数据，包含关联规则的衍生字段。
    """
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
