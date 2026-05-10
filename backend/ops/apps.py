from django.apps import AppConfig


class OpsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "ops"
    verbose_name = "Operations Monitoring"

    def ready(self):
        self._register_default_periodic_tasks()

    def _register_default_periodic_tasks(self):
        try:
            from django_celery_beat.models import CrontabSchedule, PeriodicTask

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
        except Exception:
            # Table may not exist yet (before migrations)
            pass
