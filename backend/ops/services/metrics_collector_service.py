"""
指标采集服务 —— 采集系统级别的监控指标并持久化到数据库。
类比 SpringBoot: 相当于 @Service 中的指标收集器，
类似于 Prometheus Node Exporter 的角色，
负责采集 CPU、内存、磁盘、Celery Worker、数据库/Redis/Milvus 健康状态等指标。

通常由 Celery 定时任务（beat）定期调用 collect_system_metrics + store_metrics。
"""

import logging
import socket
from datetime import timezone as tz

import psutil
from django.db import connection
from django.core.cache import cache

logger = __import__("logging").getLogger(__name__)


def collect_system_metrics():
    """
    采集当前系统的所有监控指标。

    类比 SpringBoot: 相当于 @Scheduled 定时任务中的采集逻辑，
    通过 psutil 库读取系统资源，通过直接探测检测各服务的健康状态。

    采集的指标包括:
    - cpu_percent:        CPU 使用率 (%)
    - memory_percent:     内存使用率 (%)
    - disk_percent:       磁盘使用率 (%)
    - celery_worker_count: Celery Worker 数量
    - db_healthy:         数据库连接是否正常 (1=正常, 0=异常)
    - redis_healthy:       Redis 连接是否正常 (1=正常, 0=异常)
    - milvus_healthy:      Milvus 连接是否正常 (1=正常, 0=异常)

    返回:
        list[dict]: 指标数据列表，每项包含 metric_name, value, unit, tags, collected_at。
    """
    collected_at = __import__("django.utils.timezone", fromlist=["now"]).now()
    metrics = []

    # CPU 使用率
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

    # 内存使用率
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

    # 磁盘使用率
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

    # Celery Workers 数量
    worker_count = _check_celery_workers()
    metrics.append({
        "metric_name": "celery_worker_count",
        "value": worker_count,
        "unit": "count",
        "tags": {},
        "collected_at": collected_at,
    })

    # 各服务健康检查（1 = 正常, 0 = 异常）
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
    """
    将采集到的指标批量写入数据库。

    使用 bulk_create 批量插入以提高性能。

    参数:
        metrics (list[dict]): 指标数据列表，每项来自 collect_system_metrics 的输出。
        collected_at (datetime): 统一的采集时间戳。

    返回:
        int: 成功写入的记录数。
    """
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
    """
    检测数据库连接是否正常。

    返回:
        bool: 连接正常返回 True，否则返回 False。
    """
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        return True
    except Exception:
        return False


def _check_redis():
    """
    检测 Redis 连接是否正常（通过 set + get 操作）。

    返回:
        bool: Redis 正常返回 True，否则返回 False。
    """
    try:
        cache.set("_ops_health_check", "ok", 10)
        return cache.get("_ops_health_check") == "ok"
    except Exception:
        return False


def _check_milvus():
    """
    检测 Milvus 向量数据库连接是否正常。

    通过创建临时连接、获取服务器版本号来验证可达性。

    返回:
        bool: Milvus 正常返回 True，否则返回 False。
    """
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
    """
    检测当前活跃的 Celery Worker 数量。

    通过 Celery inspect API 查询各 Worker 正在执行的任务，
    以活跃 Worker 数作为指标。

    返回:
        int: 活跃的 Celery Worker 数量，连接失败时返回 0。
    """
    try:
        from celery import current_app

        inspect = current_app.control.inspect(timeout=2.0)
        active = inspect.active()
        if active is None:
            return 0
        return len(active)
    except Exception:
        return 0
