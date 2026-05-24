"""
模型配置查询服务（类比 SpringBoot 中 @Service 的只读查询层）。
负责模型配置的列表查询、详情查询和概览统计。
概览统计包含当日/昨日调用量对比以及调用量变化百分比。
"""
from datetime import datetime, time, timedelta

from django.db.models import Count
from django.utils import timezone

from llm.models import ModelConfig, ModelInvocationLog
from llm.services.model_config_service import get_manageable_model_configs


def list_model_configs():
    """列出所有可管理的模型配置（排除 LiteLLM Legacy）。

    返回:
        QuerySet，包含预加载的微调运行记录和调用次数注解，按 capability 和 id 排序。
    """
    return get_manageable_model_configs().prefetch_related("fine_tune_runs").annotate(
        invocation_count=Count("invocation_logs")
    ).order_by("capability", "id")


def get_model_config(*, model_config_id):
    """根据主键 ID 获取可管理的模型配置。

    参数:
        model_config_id: int，模型配置的主键 ID。
    返回:
        ModelConfig 实例或 None。
    """
    return get_manageable_model_configs().prefetch_related("fine_tune_runs").filter(id=model_config_id).first()


def get_model_config_overview():
    """获取模型配置的概览统计数据。

    包括：模型总数、启用数、总调用次数、今日调用量、
    昨日调用量以及相对于昨日的调用量变化百分比。

    返回:
        dict，包含 total_models、enabled_models、total_invocation_count、
        today_invocation_count、yesterday_invocation_count、invocation_change_pct。
    """
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
