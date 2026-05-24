"""
播种周期性任务的 Django 管理命令。

类比 SpringBoot: 相当于 CommandLineRunner 或 @PostConstruct 的初始化逻辑，
从 Django management command 入口注册 Celery Beat 的定时任务调度。

该命令在系统初始化时执行，负责:
1. 创建 Celery Beat 的 crontab 调度器 (每5分钟一次)
2. 注册 ops-collect-metrics 定时任务 (采集系统指标)
3. 注册 ops-evaluate-alerts 定时任务 (评估告警规则)
4. 创建间隔调度器 (每1分钟一次)
5. 注册 risk-expire-stale-extractions 定时任务 (清理过期抽取任务)
6. 播种默认告警规则

使用方式: python manage.py seed_periodic_tasks
"""
from django.core.management.base import BaseCommand
from django_celery_beat.models import CrontabSchedule, IntervalSchedule, PeriodicTask

from ops.services import seed_default_alert_rules


class Command(BaseCommand):
    """
    播种 Celery Beat 定时任务和默认告警规则的管理命令。

    类比 SpringBoot: 相当于一个 ApplicationRunner bean，
    在应用启动后（通过命令行调用）注册调度任务和初始化规则。
    """
    help = "Seed default monitoring periodic tasks and default alert rules"

    def handle(self, *args, **options):
        """
        执行命令的主入口方法。

        参数:
            *args: 位置参数（未使用）。
            **options: 命名参数（未使用）。

        执行流程:
        1. 获取或创建"每5分钟"的 crontab 调度器 (Asia/Shanghai 时区)
        2. 注册 ops-collect-metrics 和 ops-evaluate-alerts 定时任务
        3. 获取或创建"每1分钟"的间隔调度器
        4. 注册 risk-expire-stale-extractions 定时任务
        5. 播种默认告警规则
        6. 输出成功信息到标准输出
        """
        # 创建 crontab 调度器: 每5分钟执行一次
        schedule, _ = CrontabSchedule.objects.get_or_create(
            minute="*/5",
            hour="*",
            day_of_week="*",
            day_of_month="*",
            month_of_year="*",
            timezone="Asia/Shanghai",
        )

        # 注册系统指标采集任务 (每5分钟)
        PeriodicTask.objects.get_or_create(
            name="ops-collect-metrics",
            defaults={
                "crontab": schedule,
                "task": "ops.collect_metrics_task",
                "enabled": True,
            },
        )

        # 注册告警评估任务 (每5分钟)
        PeriodicTask.objects.get_or_create(
            name="ops-evaluate-alerts",
            defaults={
                "crontab": schedule,
                "task": "ops.evaluate_alerts_task",
                "enabled": True,
            },
        )

        # 创建间隔调度器: 每1分钟执行一次 (用于清理过期任务)
        interval, _ = IntervalSchedule.objects.get_or_create(
            every=1,
            period=IntervalSchedule.MINUTES,
        )

        # 注册过期抽取任务清理 (每1分钟)
        PeriodicTask.objects.get_or_create(
            name="risk-expire-stale-extractions",
            defaults={
                "interval": interval,
                "task": "risk.expire_stale_extractions_task",
                "enabled": True,
            },
        )

        # 播种默认告警规则 (如 CPU/内存/磁盘/Celery 等规则)
        result = seed_default_alert_rules()

        self.stdout.write(
            self.style.SUCCESS(
                f"Periodic tasks seeded. Default alert rules created={result['created']} skipped={result['skipped']}."
            )
        )
