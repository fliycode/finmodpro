import logging
import socket
from datetime import timezone as tz

import psutil
from django.db import connection
from django.core.cache import cache

logger = __import__("logging").getLogger(__name__)


def collect_system_metrics():
    collected_at = __import__("django.utils.timezone", fromlist=["now"]).now()
    metrics = []

    # CPU
    try:
        cpu_percent = psutil.cpu_percent(interval=0.5)
        metrics.append({
            "metric_name": "cpu_percent",
            "value": cpu_percent,
            "unit": "%",
            "tags": {},
            "collected_at": collected_at,
        })
    except Exception as exc:
        logger.warning("Failed to collect CPU metrics: %s", exc)

    # Memory
    try:
        mem = psutil.virtual_memory()
        metrics.append({
            "metric_name": "memory_percent",
            "value": mem.percent,
            "unit": "%",
            "tags": {"total_gb": round(mem.total / (1024**3), 1)},
            "collected_at": collected_at,
        })
    except Exception as exc:
        logger.warning("Failed to collect memory metrics: %s", exc)

    # Disk
    try:
        disk = psutil.disk_usage("/")
        metrics.append({
            "metric_name": "disk_percent",
            "value": disk.percent,
            "unit": "%",
            "tags": {"total_gb": round(disk.total / (1024**3), 1)},
            "collected_at": collected_at,
        })
    except Exception as exc:
        logger.warning("Failed to collect disk metrics: %s", exc)

    # Celery workers
    worker_count = _check_celery_workers()
    metrics.append({
        "metric_name": "celery_worker_count",
        "value": worker_count,
        "unit": "count",
        "tags": {},
        "collected_at": collected_at,
    })

    # Service health (1 = ok, 0 = down)
    metrics.append({
        "metric_name": "db_healthy",
        "value": 1.0 if _check_db() else 0.0,
        "unit": "bool",
        "tags": {},
        "collected_at": collected_at,
    })
    metrics.append({
        "metric_name": "redis_healthy",
        "value": 1.0 if _check_redis() else 0.0,
        "unit": "bool",
        "tags": {},
        "collected_at": collected_at,
    })
    metrics.append({
        "metric_name": "milvus_healthy",
        "value": 1.0 if _check_milvus() else 0.0,
        "unit": "bool",
        "tags": {},
        "collected_at": collected_at,
    })

    return metrics


def store_metrics(*, metrics, collected_at):
    from ops.models import SystemMetric

    if not metrics:
        return 0

    objects = [
        SystemMetric(
            metric_name=m["metric_name"],
            value=m["value"],
            unit=m.get("unit", ""),
            tags=m.get("tags", {}),
            collected_at=m.get("collected_at", collected_at),
        )
        for m in metrics
    ]
    SystemMetric.objects.bulk_create(objects)
    return len(objects)


def _check_db():
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        return True
    except Exception:
        return False


def _check_redis():
    try:
        cache.set("_ops_health_check", "ok", 10)
        return cache.get("_ops_health_check") == "ok"
    except Exception:
        return False


def _check_milvus():
    try:
        from pymilvus import connections, utility
        from django.conf import settings

        host = getattr(settings, "MILVUS_HOST", "milvus")
        port = getattr(settings, "MILVUS_PORT", 19530)
        connections.connect(alias="_ops_health", host=host, port=port)
        utility.get_server_version(using="_ops_health")
        connections.disconnect("_ops_health")
        return True
    except Exception:
        return False


def _check_celery_workers():
    try:
        from celery import current_app

        inspect = current_app.control.inspect(timeout=2.0)
        active = inspect.active()
        if active is None:
            return 0
        return len(active)
    except Exception:
        return 0
