from django.core.management.base import BaseCommand
from django_celery_beat.models import CrontabSchedule, PeriodicTask


class Command(BaseCommand):
    help = "Seed default periodic tasks for ops monitoring"

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

        self.stdout.write(self.style.SUCCESS("Periodic tasks seeded."))
