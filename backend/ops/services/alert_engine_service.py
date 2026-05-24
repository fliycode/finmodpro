"""
告警引擎服务 —— 评估告警规则并管理告警事件。
类比 SpringBoot: 相当于 @Service 中的定时任务逻辑 + 事件处理器。

核心功能:
- evaluate_alert_rules: 拉取最新指标，逐一评估所有启用的告警规则，
  自动创建/更新/解决告警事件。通常由 Celery 定时任务调用。
- acknowledge_alert_event: 管理员手动确认一条告警事件。
"""

import logging
from datetime import timezone as tz

from django.utils.timezone import now

logger = __import__("logging").getLogger(__name__)
# 活跃告警状态集合：firing（触发中）和 acknowledged（已确认但未解决的）都算活跃
ACTIVE_ALERT_STATUSES = (
    "firing",
    "acknowledged",
)


def evaluate_alert_rules():
    """
    评估所有启用的告警规则，并根据最新指标值自动创建或解决告警事件。

    类比 SpringBoot: 相当于 @Scheduled 定时方法，由 Celery Beat 定期触发。
    流程:
    1. 加载所有启用的告警规则
    2. 批量查询每条规则对应的最新指标值
    3. 对每条规则，比较最新值与阈值
       - 如果违反条件 且 没有活跃事件: 创建新的 firing 事件
       - 如果违反条件 且 已有活跃事件: 更新 triggered_value
       - 如果未违反条件 且 有活跃事件: 将事件状态改为 resolved

    返回:
        dict: {
            "evaluated": int,  评估的规则数量
            "triggered": int,  新触发的告警数
            "resolved": int,   自动解决的告警数
        }
    """
    from ops.models import AlertEvent, AlertRule, SystemMetric

    rules = list(AlertRule.objects.filter(enabled=True))
    if not rules:
        return {"evaluated": 0, "triggered": 0, "resolved": 0}

    # 按指标名称分组，批量查询每类指标的最新值
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
            existing_open_event = AlertEvent.objects.filter(
                rule=rule,
                status__in=ACTIVE_ALERT_STATUSES,
            ).order_by("-triggered_at", "-id").first()

            if existing_open_event is None:
                AlertEvent.objects.create(
                    rule=rule,
                    status=AlertEvent.STATUS_FIRING,
                    triggered_value=metric.value,
                    triggered_at=now(),
                )
                triggered += 1
            else:
                existing_open_event.triggered_value = metric.value
                existing_open_event.save(update_fields=["triggered_value"])
        else:
            # 指标恢复正常 —— 将所有活跃事件标记为 resolved
            open_events = AlertEvent.objects.filter(
                rule=rule,
                status__in=ACTIVE_ALERT_STATUSES,
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
    """
    管理员确认一条告警事件（状态: firing -> acknowledged）。

    类比 SpringBoot: 相当于 @Service 方法，执行状态变更。

    参数:
        event_id (int): 告警事件 ID。
        user: 执行确认操作的用户实例。

    返回:
        dict: 序列化后的告警事件数据。

    抛出:
        ValueError: 当事件状态不是 firing 时抛出（只能确认触发中的事件）。
    """
    from ops.models import AlertEvent

    event = AlertEvent.objects.get(id=event_id)
    if event.status != AlertEvent.STATUS_FIRING:
        raise ValueError("只能确认状态为 firing 的告警事件。")

    event.status = AlertEvent.STATUS_ACKNOWLEDGED
    event.acknowledged_by = user
    event.save(update_fields=["status", "acknowledged_by"])
    return _serialize_alert_event(event)


def _compare_value(*, value, condition, threshold):
    """
    根据条件比较指标值与阈值。

    参数:
        value (float):    实际指标值。
        condition (str):  比较条件（gt / lt / gte / lte / eq）。
        threshold (float): 告警阈值。

    返回:
        bool: 是否满足告警条件（即是否应该触发告警）。
    """
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
    """
    将 AlertEvent 模型实例序列化为前端可用的字典格式。

    参数:
        event (AlertEvent): 告警事件模型实例。

    返回:
        dict: 序列化后的告警事件数据。
    """
    return {
        "id": event.id,
        "rule_id": event.rule_id,
        "rule_name": event.rule.name if event.rule else None,
        "severity": event.rule.severity if event.rule else None,
        "status": event.status,
        "triggered_value": event.triggered_value,
        "triggered_at": event.triggered_at.isoformat() if event.triggered_at else None,
        "resolved_at": event.resolved_at.isoformat() if event.resolved_at else None,
        "notification_channels": event.rule.notification_channels if event.rule else [],
        "acknowledged_by": event.acknowledged_by_id,
        "created_at": event.created_at.isoformat() if event.created_at else None,
    }
