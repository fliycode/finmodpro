from celery import shared_task


@shared_task(name="ops.collect_metrics_task")
def collect_metrics_task():
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
    from ops.services.alert_engine_service import evaluate_alert_rules

    result = evaluate_alert_rules()
    return result
