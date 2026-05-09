from decimal import Decimal

from llm.models import ModelInvocationLog
from llm.services.providers.base import TokenUsage


def _to_decimal(value) -> Decimal:
    return Decimal(str(value or 0))


def _normalize_usage(usage) -> TokenUsage:
    if isinstance(usage, TokenUsage):
        return usage
    if isinstance(usage, dict):
        return TokenUsage(
            request_tokens=int(usage.get("request_tokens") or 0),
            response_tokens=int(usage.get("response_tokens") or 0),
            total_tokens=int(usage.get("total_tokens") or 0),
            source=usage.get("source") or ModelInvocationLog.TOKEN_SOURCE_NONE,
            raw=dict(usage.get("raw") or {}),
        )
    return TokenUsage()


def _compute_cost_snapshots(model_config, usage: TokenUsage):
    input_unit_price_snapshot = _to_decimal(getattr(model_config, "input_price_per_million", 0))
    output_unit_price_snapshot = _to_decimal(getattr(model_config, "output_price_per_million", 0))
    request_price_snapshot = _to_decimal(getattr(model_config, "request_price", 0))

    if request_price_snapshot > 0:
        input_cost = Decimal("0")
        output_cost = Decimal("0")
        total_cost = request_price_snapshot
    else:
        input_cost = (Decimal(usage.request_tokens) / Decimal("1000000")) * input_unit_price_snapshot
        output_cost = (Decimal(usage.response_tokens) / Decimal("1000000")) * output_unit_price_snapshot
        total_cost = input_cost + output_cost

    return {
        "input_unit_price_snapshot": input_unit_price_snapshot,
        "output_unit_price_snapshot": output_unit_price_snapshot,
        "request_price_snapshot": request_price_snapshot,
        "input_cost": input_cost,
        "output_cost": output_cost,
        "total_cost": total_cost,
    }


def record_model_invocation(
    *,
    model_config,
    capability,
    alias,
    upstream_model,
    status,
    latency_ms,
    usage=None,
    error_code="",
    error_message="",
    trace_id="",
    request_id="",
    provider_request_id="",
    raw_usage=None,
    stage="",
    request_tokens=None,
    response_tokens=None,
    total_tokens=None,
    token_source=None,
):
    if usage is None and any(value is not None for value in (request_tokens, response_tokens, total_tokens, token_source, raw_usage)):
        usage = {
            "request_tokens": request_tokens,
            "response_tokens": response_tokens,
            "total_tokens": total_tokens,
            "source": token_source,
            "raw": raw_usage,
        }
    normalized_usage = _normalize_usage(usage)
    if raw_usage is not None:
        normalized_usage.raw = dict(raw_usage or {})
    total_tokens = normalized_usage.normalized_total()

    return ModelInvocationLog.objects.create(
        model_config=model_config,
        capability=capability,
        provider=model_config.provider,
        alias=alias,
        upstream_model=upstream_model,
        status=status,
        latency_ms=latency_ms,
        request_tokens=normalized_usage.request_tokens,
        response_tokens=normalized_usage.response_tokens,
        total_tokens=total_tokens,
        token_source=normalized_usage.source,
        raw_usage=normalized_usage.raw,
        provider_request_id=provider_request_id,
        error_code=error_code,
        error_message=error_message,
        trace_id=trace_id,
        request_id=request_id,
        stage=stage,
        **_compute_cost_snapshots(model_config, normalized_usage),
    )
