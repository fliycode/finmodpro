from django.core.management.base import BaseCommand
from django_celery_beat.models import CrontabSchedule, IntervalSchedule, PeriodicTask

from ops.services import seed_default_alert_rules


class Command(BaseCommand):
    help = "Seed default monitoring periodic tasks and default alert rules"

    def handle(self, *args, **options):
        schedule, _ = CrontabSchedule.objects.get_or_create(
            minute="*/5",
            hour="*",
            day_of_week="*",
            day_of_month="*",
            month_of_year="*",
            timezone="Asia/Shanghai",
        )

        PeriodicTask.objects.get_or_create(
            name="ops-collect-metrics",
            defaults={
                "crontab": schedule,
                "task": "ops.collect_metrics_task",
                "enabled": True,
            },
        )

        PeriodicTask.objects.get_or_create(
            name="ops-evaluate-alerts",
            defaults={
                "crontab": schedule,
                "task": "ops.evaluate_alerts_task",
                "enabled": True,
            },
        )

        interval, _ = IntervalSchedule.objects.get_or_create(
            every=1,
            period=IntervalSchedule.MINUTES,
        )

        PeriodicTask.objects.get_or_create(
            name="risk-expire-stale-extractions",
            defaults={
                "interval": interval,
                "task": "risk.expire_stale_extractions_task",
                "enabled": True,
            },
        )

        result = seed_default_alert_rules()

        self.stdout.write(
            self.style.SUCCESS(
                f"Periodic tasks seeded. Default alert rules created={result['created']} skipped={result['skipped']}."
            )
        )
