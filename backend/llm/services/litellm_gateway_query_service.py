"""
LiteLLM gateway analytics query service.

All functions return plain dicts suitable for JSON serialization.
No raw prompt or response data is ever exposed.
"""
from collections import Counter, defaultdict
from datetime import timedelta

from django.db.models import Avg, Count, Sum
from django.utils import timezone

from llm.models import LiteLLMSyncEvent, ModelConfig, ModelInvocationLog

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_TIME_PRESETS = {
    "1h": timedelta(hours=1),
    "24h": timedelta(hours=24),
    "7d": timedelta(days=7),
    "30d": timedelta(days=30),
}

_LATENCY_BUCKETS = [
    ("<100ms", 0, 100),
    ("100–500ms", 100, 500),
    ("500ms–1s", 500, 1000),
    ("1–3s", 1000, 3000),
    (">3s", 3000, None),
]


def _window_start(time_preset: str | None):
    delta = _TIME_PRESETS.get(time_preset or "24h", _TIME_PRESETS["24h"])
    return timezone.now() - delta


def _parse_filters(filters: dict | None):
    filters = filters or {}
    return {
        "model": filters.get("model") or None,
        "status": filters.get("status") or None,
        "time": filters.get("time") or "24h",
    }


def _apply_filters(qs, filters: dict):
    start = _window_start(filters.get("time"))
    qs = qs.filter(created_at__gte=start)
    if filters.get("model"):
        qs = qs.filter(alias=filters["model"])
    if filters.get("status"):
        qs = qs.filter(status=filters["status"])
    return qs


def _pricing_map() -> dict:
    """Return {model_config_id: (input_price_per_million, output_price_per_million)}."""
    pricing = {}
    for mc in ModelConfig.objects.only("id", "options"):
        litellm_opts = (mc.options or {}).get("litellm", {})
        inp = litellm_opts.get("input_price_per_million", 0) or 0
        out = litellm_opts.get("output_price_per_million", 0) or 0
        pricing[mc.id] = (float(inp), float(out))
    return pricing


def _estimate_cost(log_rows, pricing: dict) -> float:
    total = 0.0
    for row in log_rows:
        mc_id = row.model_config_id
        if mc_id not in pricing:
            continue
        inp_price, out_price = pricing[mc_id]
        total += (row.request_tokens / 1_000_000) * inp_price
        total += (row.response_tokens / 1_000_000) * out_price
    return total


def _serialize_log(log) -> dict:
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
# Summary (Dashboard)
# ---------------------------------------------------------------------------

def get_gateway_summary() -> dict:
    """Return data for the LiteLLM gateway dashboard."""
    window_start = _window_start("24h")
    litellm_configs = ModelConfig.objects.filter(provider=ModelConfig.PROVIDER_LITELLM)
    active_count = litellm_configs.filter(is_active=True).count()
    total_count = litellm_configs.count()

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

    # Recent sync event
    latest_sync = LiteLLMSyncEvent.objects.order_by("-created_at", "-id").first()
    recent_sync = None
    if latest_sync is not None:
        recent_sync = {
            "status": latest_sync.status,
            "message": latest_sync.message,
            "created_at": latest_sync.created_at.isoformat(),
        }

    # Traffic in last 24h
    recent_logs = ModelInvocationLog.objects.filter(created_at__gte=window_start)
    total = recent_logs.count()
    failed = recent_logs.filter(status=ModelInvocationLog.STATUS_FAILED).count()
    error_rate = round((failed / total * 100) if total else 0.0, 2)
    traffic = {
        "request_count": total,
        "failed_count": failed,
        "error_rate_pct": error_rate,
    }

    # Top models by request count
    top_qs = (
        recent_logs.values("alias")
        .annotate(request_count=Count("id"))
        .order_by("-request_count")[:10]
    )
    top_models = [
        {"alias": row["alias"], "request_count": row["request_count"]}
        for row in top_qs
    ]

    # Recent failed invocations (sample)
    recent_errors = [
        _serialize_log(log)
        for log in recent_logs.filter(
            status=ModelInvocationLog.STATUS_FAILED
        ).order_by("-created_at")[:10]
    ]

    return {
        "gateway": gateway,
        "recent_sync": recent_sync,
        "traffic": traffic,
        "top_models": top_models,
        "recent_errors": recent_errors,
    }


# ---------------------------------------------------------------------------
# Logs
# ---------------------------------------------------------------------------

def get_logs(filters: dict | None = None, page: int = 1, page_size: int = 50) -> dict:
    """Return filtered request-level log rows. No raw prompt/response."""
    filters = _parse_filters(filters)
    qs = _apply_filters(ModelInvocationLog.objects.all(), filters)
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
    """Return aggregate metrics honoring the same filters as get_logs."""
    filters = _parse_filters(filters)
    qs = _apply_filters(ModelInvocationLog.objects.all(), filters)

    total = qs.count()
    failed = qs.filter(status=ModelInvocationLog.STATUS_FAILED).count()
    error_rate = round((failed / total * 100) if total else 0.0, 2)
    avg_latency = qs.aggregate(v=Avg("latency_ms"))["v"] or 0.0

    # Error breakdown by error_code
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

    # Latency distribution buckets
    latency_buckets = []
    for label, lo, hi in _LATENCY_BUCKETS:
        bucket_qs = qs.filter(latency_ms__gte=lo)
        if hi is not None:
            bucket_qs = bucket_qs.filter(latency_ms__lt=hi)
        latency_buckets.append({"label": label, "count": bucket_qs.count()})

    return {
        "filters": filters,
        "total_requests": total,
        "error_rate_pct": error_rate,
        "avg_latency_ms": round(float(avg_latency), 2),
        "error_breakdown": error_breakdown,
        "latency_buckets": latency_buckets,
    }


# ---------------------------------------------------------------------------
# Traces
# ---------------------------------------------------------------------------

def get_trace(trace_id: str) -> dict | None:
    """Return a trace-level view of all log rows for trace_id, or None."""
    logs = list(
        ModelInvocationLog.objects.filter(trace_id=trace_id).order_by("created_at", "id")
    )
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
# Errors
# ---------------------------------------------------------------------------

def get_errors(time_preset: str = "24h") -> dict:
    """Return aggregated error types plus recent error samples."""
    window_start = _window_start(time_preset)
    failed_qs = ModelInvocationLog.objects.filter(
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
# Costs
# ---------------------------------------------------------------------------

def get_costs_summary(filters: dict | None = None) -> dict:
    """Return token usage and estimated cost summary."""
    filters = _parse_filters(filters)
    qs = _apply_filters(ModelInvocationLog.objects.all(), filters)

    agg = qs.aggregate(
        total_requests=Count("id"),
        total_req_tokens=Sum("request_tokens"),
        total_resp_tokens=Sum("response_tokens"),
    )
    total_requests = agg["total_requests"] or 0
    total_request_tokens = agg["total_req_tokens"] or 0
    total_response_tokens = agg["total_resp_tokens"] or 0

    # Compute cost per model_config_id group
    pricing = _pricing_map()
    by_config = (
        qs.values("model_config_id")
        .annotate(req_tokens=Sum("request_tokens"), resp_tokens=Sum("response_tokens"))
    )
    estimated_input_cost = 0.0
    estimated_output_cost = 0.0
    for row in by_config:
        mc_id = row["model_config_id"]
        inp_price, out_price = pricing.get(mc_id, (0.0, 0.0))
        estimated_input_cost += ((row["req_tokens"] or 0) / 1_000_000) * inp_price
        estimated_output_cost += ((row["resp_tokens"] or 0) / 1_000_000) * out_price

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
    """Return usage/cost aggregated over time buckets."""
    filters = _parse_filters(filters)
    time_preset = filters.get("time", "24h")
    qs = _apply_filters(ModelInvocationLog.objects.all(), filters)

    # Choose bucket granularity based on time window
    if time_preset in ("1h", "24h"):
        bucket_hours = 1
        fmt = "%Y-%m-%dT%H:00"
    elif time_preset == "7d":
        bucket_hours = 6
        fmt = "%Y-%m-%dT%H:00"
    else:  # 30d
        bucket_hours = 24
        fmt = "%Y-%m-%d"

    pricing = _pricing_map()

    # Group logs by bucket
    buckets: dict = defaultdict(lambda: {"request_count": 0, "estimated_cost": 0.0})
    for log in qs.only(
        "created_at", "model_config_id", "request_tokens", "response_tokens"
    ):
        # Floor to bucket
        ts = log.created_at
        floored_hour = (ts.hour // bucket_hours) * bucket_hours
        bucket_key = ts.replace(hour=floored_hour, minute=0, second=0, microsecond=0).strftime(fmt)

        inp_price, out_price = pricing.get(log.model_config_id, (0.0, 0.0))
        cost = (
            (log.request_tokens / 1_000_000) * inp_price
            + (log.response_tokens / 1_000_000) * out_price
        )
        buckets[bucket_key]["request_count"] += 1
        buckets[bucket_key]["estimated_cost"] += cost

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

    return {"filters": filters, "granularity_hours": bucket_hours, "points": points}


def get_costs_models(filters: dict | None = None) -> dict:
    """Return per-model usage/cost breakdown with request share."""
    filters = _parse_filters(filters)
    qs = _apply_filters(ModelInvocationLog.objects.all(), filters)

    # Aggregate by alias + model_config_id
    by_alias = (
        qs.values("alias", "model_config_id")
        .annotate(
            request_count=Count("id"),
            req_tokens=Sum("request_tokens"),
            resp_tokens=Sum("response_tokens"),
        )
        .order_by("-request_count")
    )
    total_requests = qs.count()
    pricing = _pricing_map()

    models = []
    for row in by_alias:
        mc_id = row["model_config_id"]
        inp_price, out_price = pricing.get(mc_id, (0.0, 0.0))
        req_tokens = row["req_tokens"] or 0
        resp_tokens = row["resp_tokens"] or 0
        input_cost = (req_tokens / 1_000_000) * inp_price
        output_cost = (resp_tokens / 1_000_000) * out_price
        total_cost = input_cost + output_cost
        request_count = row["request_count"]
        share = round((request_count / total_requests * 100) if total_requests else 0.0, 2)
        models.append(
            {
                "alias": row["alias"],
                "request_count": request_count,
                "request_share_pct": share,
                "total_request_tokens": req_tokens,
                "total_response_tokens": resp_tokens,
                "estimated_input_cost": round(input_cost, 6),
                "estimated_output_cost": round(output_cost, 6),
                "estimated_total_cost": round(total_cost, 6),
            }
        )

    return {"filters": filters, "total_requests": total_requests, "models": models}
