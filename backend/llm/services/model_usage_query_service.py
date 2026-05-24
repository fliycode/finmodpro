"""
模型用量分析查询服务（类比 SpringBoot 中 @Service 的分析层）。
提供 LLM 网关的各类聚合分析数据：
- 概览（网关健康状态、流量、Top 模型、最近错误）
- 日志（分页查询、摘要聚合）
- 链路追踪
- 错误分析
- 成本计算（汇总、时序、按模型分组）
"""
from collections import defaultdict
from datetime import timedelta

from django.db.models import Avg, Count, Q, Sum
from django.db.models.functions import TruncDay, TruncHour, TruncMinute
from django.utils import timezone

from llm.models import ModelConfig, ModelInvocationLog

# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------

# 时间窗口预设映射：预设名 -> timedelta
_TIME_PRESETS = {
    "1h": timedelta(hours=1),
    "24h": timedelta(hours=24),
    "7d": timedelta(days=7),
    "30d": timedelta(days=30),
}

# 延迟分桶定义：(标签, 下限ms, 上限ms)，上限为 None 表示到无穷
_LATENCY_BUCKETS = [
    ("<100ms", 0, 100),
    ("100-500ms", 100, 500),
    ("500ms-1s", 500, 1000),
    ("1-3s", 1000, 3000),
    (">3s", 3000, None),
]


def _window_start(time_preset: str | None):
    """将时间预设字符串转换为时间窗口的起始时刻。

    参数:
        time_preset: str，时间预设名（'1h' / '24h' / '7d' / '30d'）。
    返回:
        datetime，窗口起始时间。
    """
    delta = _TIME_PRESETS.get(time_preset or "24h", _TIME_PRESETS["24h"])
    return timezone.now() - delta


def _parse_filters(filters: dict | None):
    """解析并规范化查询筛选条件。

    参数:
        filters: dict 或 None，原始筛选条件。
    返回:
        dict，包含 model、status、time 三个规范化后的筛选值。
    """
    filters = filters or {}
    return {
        "model": filters.get("model") or None,
        "status": filters.get("status") or None,
        "time": filters.get("time") or "24h",
    }


def _managed_qs():
    """获取模型调用日志的基础查询集。

    返回:
        QuerySet，所有 ModelInvocationLog 记录。
    """
    return ModelInvocationLog.objects.all()


def _apply_filters(qs, filters: dict):
    """将筛选条件应用到查询集上。

    参数:
        qs: QuerySet，基础查询集。
        filters: dict，包含 model、status、time 筛选条件。
    返回:
        QuerySet，筛选后的查询集。
    """
    start = _window_start(filters.get("time"))
    qs = qs.filter(created_at__gte=start)
    if filters.get("model"):
        qs = qs.filter(alias=filters["model"])
    if filters.get("status"):
        qs = qs.filter(status=filters["status"])
    return qs


def _pricing_map() -> dict:
    """构建模型配置 ID -> (输入单价, 输出单价) 的映射字典。

    用于在 Python 侧快速查找定价并估算成本。

    返回:
        dict，key 为 model_config_id，value 为 (input_price, output_price) 元组。
    """
    pricing = {}
    for mc in ModelConfig.objects.all().only(
        "id",
        "input_price_per_million",
        "output_price_per_million",
    ):
        pricing[mc.id] = (
            float(mc.input_price_per_million or 0),
            float(mc.output_price_per_million or 0),
        )
    return pricing


def _apply_pricing(row: dict, pricing: dict) -> tuple[float, float]:
    """根据定价映射为单行聚合数据计算估算成本。

    参数:
        row: dict，必须包含 model_config_id、req_tokens、resp_tokens 键。
        pricing: dict，由 _pricing_map() 返回的定价映射。
    返回:
        (float, float)，(输入成本估算, 输出成本估算)。
    """
    inp_price, out_price = pricing.get(row.get("model_config_id"), (0.0, 0.0))
    req_tokens = row.get("req_tokens") or 0
    resp_tokens = row.get("resp_tokens") or 0
    return (req_tokens / 1_000_000) * inp_price, (resp_tokens / 1_000_000) * out_price


def _resolve_costs(row: dict, pricing: dict) -> tuple[float, float]:
    """解析单行的成本数据：优先使用 DB 中已存储的成本快照，否则按定价估算。

    参数:
        row: dict，聚合行数据。
        pricing: dict，定价映射。
    返回:
        (float, float)，(输入成本, 输出成本)。
    """
    input_cost = float(row.get("input_cost_sum") or 0)
    output_cost = float(row.get("output_cost_sum") or 0)
    total_cost = float(row.get("total_cost_sum") or 0)
    if input_cost or output_cost or total_cost:
        return input_cost, output_cost
    return _apply_pricing(row, pricing)


def _serialize_log(log) -> dict:
    """将单条 ModelInvocationLog 序列化为字典。

    参数:
        log: ModelInvocationLog 实例。
    返回:
        dict，包含关键字段的序列化结果。
    """
    return {
        "time": log.created_at.isoformat(),
        "alias": log.alias,
        "upstream_model": log.upstream_model,
        "capability": log.capability,
        "stage": log.stage,
        "latency_ms": log.latency_ms,
        "request_tokens": log.request_tokens,
        "response_tokens": log.response_tokens,
        "status": log.status,
        "error_code": log.error_code,
        "error_message": log.error_message,
        "trace_id": log.trace_id,
        "request_id": log.request_id,
    }


# ---------------------------------------------------------------------------
# 概览（Dashboard）
# ---------------------------------------------------------------------------

def get_gateway_summary() -> dict:
    """获取网关概览数据。

    包含：
    - 网关健康状态（healthy/configured/missing）
    - 24h 内流量统计（请求数、失败数、错误率）
    - Top 10 模型（按请求量）
    - 最近 10 条失败日志

    返回:
        dict，包含 gateway、traffic、top_models、recent_errors。
    """
    window_start = _window_start("24h")
    managed_configs = ModelConfig.objects.all()
    active_count = managed_configs.filter(is_active=True).count()
    total_count = managed_configs.count()

    if active_count:
        gw_status = "healthy"
    elif total_count:
        gw_status = "configured"
    else:
        gw_status = "missing"

    gateway = {
        "status": gw_status,
        "active_model_count": active_count,
        "total_model_count": total_count,
    }

    recent_logs = _managed_qs().filter(created_at__gte=window_start)
    traffic_agg = recent_logs.aggregate(
        total=Count("id"),
        failed=Count("id", filter=Q(status=ModelInvocationLog.STATUS_FAILED)),
    )
    total = traffic_agg["total"] or 0
    failed = traffic_agg["failed"] or 0
    error_rate = round((failed / total * 100) if total else 0.0, 2)
    traffic = {
        "request_count": total,
        "failed_count": failed,
        "error_rate_pct": error_rate,
    }

    # Top 模型按请求量排名
    top_qs = (
        recent_logs.values("alias")
        .annotate(request_count=Count("id"))
        .order_by("-request_count")[:10]
    )
    top_models = [
        {"alias": row["alias"], "request_count": row["request_count"]}
        for row in top_qs
    ]

    # 最近失败的调用（采样）
    recent_errors = [
        _serialize_log(log)
        for log in recent_logs.filter(
            status=ModelInvocationLog.STATUS_FAILED
        ).order_by("-created_at")[:10]
    ]

    return {
        "gateway": gateway,
        "traffic": traffic,
        "top_models": top_models,
        "recent_errors": recent_errors,
    }


# ---------------------------------------------------------------------------
# 日志
# ---------------------------------------------------------------------------

def get_logs(filters: dict | None = None, page: int = 1, page_size: int = 50) -> dict:
    """获取筛选后的分页调用日志。

    不返回原始 prompt/response 内容。

    参数:
        filters: dict 或 None，筛选条件（model、status、time）。
        page: int，页码（从 1 开始）。
        page_size: int，每页条数（最大 200）。
    返回:
        dict，包含 filters、total、page、page_size、logs 列表。
    """
    filters = _parse_filters(filters)
    qs = _apply_filters(_managed_qs(), filters)
    total = qs.count()
    offset = (page - 1) * page_size
    rows = qs.order_by("-created_at")[offset : offset + page_size]
    return {
        "filters": filters,
        "total": total,
        "page": page,
        "page_size": page_size,
        "logs": [_serialize_log(log) for log in rows],
    }


def get_logs_summary(filters: dict | None = None) -> dict:
    """获取日志聚合摘要指标。

    包含请求总量、错误率、平均延迟、延迟分桶分布、错误码分布。

    参数:
        filters: dict 或 None，筛选条件。
    返回:
        dict，包含 total_requests、error_rate_pct、avg_latency_ms、error_breakdown、latency_buckets。
    """
    filters = _parse_filters(filters)
    qs = _apply_filters(_managed_qs(), filters)

    agg = qs.aggregate(
        total=Count("id"),
        failed=Count("id", filter=Q(status=ModelInvocationLog.STATUS_FAILED)),
        avg_latency=Avg("latency_ms"),
        **{
            f"bucket_{i}": Count(
                "id",
                filter=(
                    Q(latency_ms__gte=lo, latency_ms__lt=hi)
                    if hi is not None
                    else Q(latency_ms__gte=lo)
                ),
            )
            for i, (label, lo, hi) in enumerate(_LATENCY_BUCKETS)
        },
    )

    total = agg["total"] or 0
    failed = agg["failed"] or 0
    error_rate = round((failed / total * 100) if total else 0.0, 2)
    avg_latency = agg["avg_latency"] or 0.0

    # 按错误码统计失败分布
    error_qs = (
        qs.filter(status=ModelInvocationLog.STATUS_FAILED)
        .values("error_code")
        .annotate(count=Count("id"))
        .order_by("-count")
    )
    error_breakdown = [
        {"error_code": row["error_code"] or "unknown", "count": row["count"]}
        for row in error_qs
    ]

    latency_buckets = [
        {"label": label, "count": agg[f"bucket_{i}"]}
        for i, (label, lo, hi) in enumerate(_LATENCY_BUCKETS)
    ]

    return {
        "filters": filters,
        "total_requests": total,
        "error_rate_pct": error_rate,
        "avg_latency_ms": round(float(avg_latency), 2),
        "error_breakdown": error_breakdown,
        "latency_buckets": latency_buckets,
    }


# ---------------------------------------------------------------------------
# 链路追踪
# ---------------------------------------------------------------------------

def get_trace(trace_id: str) -> dict | None:
    """根据 trace_id 获取完整调用链的所有日志。

    参数:
        trace_id: str，链路追踪唯一标识。
    返回:
        dict 或 None，包含 trace_id、status、时间范围、logs 列表。
        若 trace_id 无关联日志则返回 None。
    """
    logs = list(_managed_qs().filter(trace_id=trace_id).order_by("created_at", "id"))
    if not logs:
        return None

    statuses = {log.status for log in logs}
    if ModelInvocationLog.STATUS_FAILED in statuses:
        trace_status = ModelInvocationLog.STATUS_FAILED
    else:
        trace_status = ModelInvocationLog.STATUS_SUCCESS

    return {
        "trace_id": trace_id,
        "status": trace_status,
        "started_at": logs[0].created_at.isoformat(),
        "ended_at": logs[-1].created_at.isoformat(),
        "logs": [_serialize_log(log) for log in logs],
    }


# ---------------------------------------------------------------------------
# 错误分析
# ---------------------------------------------------------------------------

def get_errors(time_preset: str = "24h") -> dict:
    """获取指定时间窗口内的聚合错误类型及最近错误样本。

    参数:
        time_preset: str，时间窗口预设名。
    返回:
        dict，包含 total_failed_requests、error_types（错误码分布）、recent_errors（最近 20 条）。
    """
    window_start = _window_start(time_preset)
    failed_qs = _managed_qs().filter(
        status=ModelInvocationLog.STATUS_FAILED,
        created_at__gte=window_start,
    )
    total_failed = failed_qs.count()

    error_type_qs = (
        failed_qs.values("error_code")
        .annotate(count=Count("id"))
        .order_by("-count")
    )
    error_types = [
        {"error_code": row["error_code"] or "unknown", "count": row["count"]}
        for row in error_type_qs
    ]

    recent_errors = [_serialize_log(log) for log in failed_qs.order_by("-created_at")[:20]]

    return {
        "total_failed_requests": total_failed,
        "error_types": error_types,
        "recent_errors": recent_errors,
    }


# ---------------------------------------------------------------------------
# 成本分析
# ---------------------------------------------------------------------------

def get_costs_summary(filters: dict | None = None) -> dict:
    """获取 Token 用量和估算成本汇总。

    参数:
        filters: dict 或 None，筛选条件。
    返回:
        dict，包含 total_requests、token 用量和 estimated 成本。
    """
    filters = _parse_filters(filters)
    qs = _apply_filters(_managed_qs(), filters)

    pricing = _pricing_map()
    by_config = list(
        qs.values("model_config_id")
        .annotate(
            count=Count("id"),
            req_tokens=Sum("request_tokens"),
            resp_tokens=Sum("response_tokens"),
            input_cost_sum=Sum("input_cost"),
            output_cost_sum=Sum("output_cost"),
            total_cost_sum=Sum("total_cost"),
        )
    )
    total_requests = sum(row["count"] for row in by_config)
    total_request_tokens = sum(row["req_tokens"] or 0 for row in by_config)
    total_response_tokens = sum(row["resp_tokens"] or 0 for row in by_config)
    estimated_input_cost = 0.0
    estimated_output_cost = 0.0
    for row in by_config:
        inp, out = _resolve_costs(row, pricing)
        estimated_input_cost += inp
        estimated_output_cost += out

    return {
        "filters": filters,
        "total_requests": total_requests,
        "total_request_tokens": total_request_tokens,
        "total_response_tokens": total_response_tokens,
        "estimated_input_cost": round(estimated_input_cost, 6),
        "estimated_output_cost": round(estimated_output_cost, 6),
        "estimated_total_cost": round(estimated_input_cost + estimated_output_cost, 6),
    }


def get_costs_timeseries(filters: dict | None = None) -> dict:
    """获取按时间桶聚合的用量/成本时序数据。

    时间颗粒度根据 time 预设自动选择：
    - 1h: 分钟级 (TruncMinute)
    - 24h: 小时级 (TruncHour)
    - 7d: 6小时级 (TruncHour + Python 后处理)
    - 30d: 天级 (TruncDay)

    参数:
        filters: dict 或 None，筛选条件。
    返回:
        dict，包含 granularity_hours/minutes 和 points 列表。
    """
    filters = _parse_filters(filters)
    time_preset = filters.get("time", "24h")
    qs = _apply_filters(_managed_qs(), filters)

    # 根据时间窗口选择 DB 截断函数和输出格式
    # 1h 使用分钟级分桶以便观察小时内流量
    # 7d 使用小时级 DB 截断后在 Python 中合并为 6 小时桶
    if time_preset == "1h":
        trunc_fn = TruncMinute("created_at")
        bucket_minutes = 1
        bucket_hours = None
        fmt = "%Y-%m-%dT%H:%M"
    elif time_preset == "24h":
        trunc_fn = TruncHour("created_at")
        bucket_hours = 1
        bucket_minutes = None
        fmt = "%Y-%m-%dT%H:00"
    elif time_preset == "7d":
        trunc_fn = TruncHour("created_at")
        bucket_hours = 6
        bucket_minutes = None
        fmt = "%Y-%m-%dT%H:00"
    else:  # 30d
        trunc_fn = TruncDay("created_at")
        bucket_hours = 24
        bucket_minutes = None
        fmt = "%Y-%m-%d"

    pricing = _pricing_map()

    # 在 DB 中按 (time_bucket, model_config_id) 聚合
    db_rows = (
        qs.annotate(time_bucket=trunc_fn)
        .values("time_bucket", "model_config_id")
        .annotate(
            request_count=Count("id"),
            req_tokens=Sum("request_tokens"),
            resp_tokens=Sum("response_tokens"),
            input_cost_sum=Sum("input_cost"),
            output_cost_sum=Sum("output_cost"),
            total_cost_sum=Sum("total_cost"),
        )
        .order_by("time_bucket")
    )

    # Python 后处理：应用定价并将数据合并到目标粒度
    buckets: dict = defaultdict(lambda: {"request_count": 0, "estimated_cost": 0.0})
    for row in db_rows:
        ts = row["time_bucket"]
        if bucket_hours == 6:
            floored_hour = (ts.hour // 6) * 6
            ts = ts.replace(hour=floored_hour, minute=0, second=0, microsecond=0)
        bucket_key = ts.strftime(fmt)

        inp_cost, out_cost = _resolve_costs(row, pricing)
        buckets[bucket_key]["request_count"] += row["request_count"]
        buckets[bucket_key]["estimated_cost"] += inp_cost + out_cost

    points = sorted(
        [
            {
                "bucket": key,
                "request_count": val["request_count"],
                "estimated_cost": round(val["estimated_cost"], 6),
            }
            for key, val in buckets.items()
        ],
        key=lambda p: p["bucket"],
    )

    return {
        "filters": filters,
        "granularity_hours": bucket_hours,
        "granularity_minutes": bucket_minutes,
        "points": points,
    }


def get_costs_models(filters: dict | None = None) -> dict:
    """获取按模型分组的用量和成本明细。

    每个模型包含请求量、占比百分比、Token 用量和估算成本。

    参数:
        filters: dict 或 None，筛选条件。
    返回:
        dict，包含 total_requests 和 models 列表。
    """
    filters = _parse_filters(filters)
    qs = _apply_filters(_managed_qs(), filters)

    # 按 alias + model_config_id 聚合
    by_alias = list(
        qs.values("alias", "model_config_id")
        .annotate(
            request_count=Count("id"),
            req_tokens=Sum("request_tokens"),
            resp_tokens=Sum("response_tokens"),
            input_cost_sum=Sum("input_cost"),
            output_cost_sum=Sum("output_cost"),
            total_cost_sum=Sum("total_cost"),
        )
        .order_by("-request_count")
    )
    total_requests = sum(row["request_count"] for row in by_alias)
    pricing = _pricing_map()

    models = []
    for row in by_alias:
        inp_cost, out_cost = _resolve_costs(row, pricing)
        total_cost = inp_cost + out_cost
        request_count = row["request_count"]
        share = round((request_count / total_requests * 100) if total_requests else 0.0, 2)
        models.append(
            {
                "alias": row["alias"],
                "request_count": request_count,
                "request_share_pct": share,
                "total_request_tokens": row["req_tokens"] or 0,
                "total_response_tokens": row["resp_tokens"] or 0,
                "estimated_input_cost": round(inp_cost, 6),
                "estimated_output_cost": round(out_cost, 6),
                "estimated_total_cost": round(total_cost, 6),
            }
        )

    return {"filters": filters, "total_requests": total_requests, "models": models}
