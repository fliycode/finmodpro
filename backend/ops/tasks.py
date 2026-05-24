"""
运维监控异步任务 —— 定义定时采集和告警评估的 Celery 任务。

类比 SpringBoot: 相当于 @Scheduled 注解的定时方法，
由 Celery Beat 调度器定期触发执行。

任务:
- collect_metrics_task:  采集系统指标 (CPU/内存/磁盘/服务健康状态)
- evaluate_alerts_task:  评估告警规则 (比较指标值与阈值，触发或解决告警)
"""
from celery import shared_task


@shared_task(name="ops.collect_metrics_task")
def collect_metrics_task():
    """
    采集系统监控指标并写入数据库。

    类比 SpringBoot: 相当于 @Scheduled(fixedRate = 5min) 的定时采集方法。
    采集内容包括 CPU 使用率、内存使用率、磁盘使用率、
    Celery Worker 数量、数据库/Redis/Milvus 健康状态。

    返回:
        dict: {"collected": int} 成功写入的指标记录数。
    """
    from ops.services.metrics_collector_service import (
        collect_system_metrics,
        store_metrics,
    )
    from django.utils.timezone import now

    collected_at = now()
    metrics = collect_system_metrics()
    count = store_metrics(metrics=metrics, collected_at=collected_at)
    return {"collected": count}


@shared_task(name="ops.evaluate_alerts_task")
def evaluate_alerts_task():
    """
    评估所有启用的告警规则并根据最新指标值触发或解决告警。

    类比 SpringBoot: 相当于 @Scheduled 的告警评估方法。
    流程:
    1. 加载所有启用规则
    2. 查询每类指标的最新值
    3. 逐条比较是否违反阈值
    4. 创建/更新/解决告警事件

    返回:
        dict: {"evaluated": int, "triggered": int, "resolved": int}
              分别代表评估的规则数、新触发的告警数、自动解决的告警数。
    """
    from ops.services.alert_engine_service import evaluate_alert_rules

    result = evaluate_alert_rules()
    return result
