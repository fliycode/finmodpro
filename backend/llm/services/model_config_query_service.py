from datetime import datetime, time, timedelta

from django.db.models import Count
from django.utils import timezone

from llm.models import ModelConfig, ModelInvocationLog
from llm.services.model_config_service import get_manageable_model_configs


def list_model_configs():
    return get_manageable_model_configs().prefetch_related("fine_tune_runs").annotate(
        invocation_count=Count("invocation_logs")
    ).order_by("capability", "id")


def get_model_config(*, model_config_id):
    return get_manageable_model_configs().prefetch_related("fine_tune_runs").filter(id=model_config_id).first()


def get_model_config_overview():
    today = timezone.localdate()
    today_start = timezone.make_aware(datetime.combine(today, time.min))
    tomorrow_start = timezone.make_aware(datetime.combine(today + timedelta(days=1), time.min))
    yesterday_start = timezone.make_aware(datetime.combine(today - timedelta(days=1), time.min))

    total_invocation_count = ModelInvocationLog.objects.count()
    today_invocation_count = ModelInvocationLog.objects.filter(
        created_at__gte=today_start,
        created_at__lt=tomorrow_start,
    ).count()
    yesterday_invocation_count = ModelInvocationLog.objects.filter(
        created_at__gte=yesterday_start,
        created_at__lt=today_start,
    ).count()

    invocation_change_pct = None
    if yesterday_invocation_count > 0:
        invocation_change_pct = round(
            ((today_invocation_count - yesterday_invocation_count) / yesterday_invocation_count) * 100,
            1,
        )

    manageable_model_configs = get_manageable_model_configs()

    return {
        "total_models": manageable_model_configs.count(),
        "enabled_models": manageable_model_configs.filter(is_active=True).count(),
        "total_invocation_count": total_invocation_count,
        "today_invocation_count": today_invocation_count,
        "yesterday_invocation_count": yesterday_invocation_count,
        "invocation_change_pct": invocation_change_pct,
    }
