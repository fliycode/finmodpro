"""
模型调用日志服务（类比 SpringBoot 中 @Service 的审计日志记录层）。
负责将每次 LLM API 调用的结果记录到 ModelInvocationLog 表中，
包括用量统计、成本计算、状态和错误信息等。
"""
from decimal import Decimal

from llm.models import ModelInvocationLog
from llm.services.providers.base import TokenUsage


def _to_decimal(value) -> Decimal:
    """将数值转为 Decimal 类型。

    参数:
        value: 数值类型的输入。
    返回:
        Decimal，转换后的值，None 或 0 转为 Decimal("0")。
    """
    return Decimal(str(value or 0))


def _normalize_usage(usage) -> TokenUsage:
    """将不同格式的 usage 数据统一规范化为 TokenUsage 对象。

    参数:
        usage: TokenUsage 实例、dict 或 None。
            - 若已是 TokenUsage，直接返回。
            - 若为 dict，从中提取 request_tokens、response_tokens 等字段构造 TokenUsage。
            - 否则返回空 TokenUsage。
    返回:
        TokenUsage，规范化后的用量对象。
    """
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
    """根据模型定价和 Token 用量计算成本快照。

    优先使用按次请求定价（request_price），若未设置则按每百万 token 单价计算。

    参数:
        model_config: ModelConfig 实例，包含定价信息。
        usage: TokenUsage，本次调用的 Token 用量。
    返回:
        dict，包含 input_unit_price_snapshot、output_unit_price_snapshot、
        request_price_snapshot、input_cost、output_cost、total_cost。
    """
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
    """记录一次模型调用日志到数据库。

    支持两种方式传入 Token 用量：
    1. 通过 usage 参数传入统一的 TokenUsage 对象。
    2. 通过独立的 request_tokens / response_tokens / total_tokens / token_source / raw_usage 参数。
    当 usage 为 None 但有独立参数时，内部自动包装为 TokenUsage。

    参数:
        model_config: ModelConfig 实例，关联的模型配置（可为 None）。
        capability: str，能力类型。
        alias: str，模型别名。
        upstream_model: str，上游模型标识。
        status: str，调用状态（'success' 或 'failed'）。
        latency_ms: int，调用延迟（毫秒）。
        usage: TokenUsage 实例或 None，统一用量数据。
        error_code: str，错误码（失败时填写）。
        error_message: str，错误信息（失败时填写）。
        trace_id: str，链路追踪 ID。
        request_id: str，请求 ID。
        provider_request_id: str，供应商返回的请求标识。
        raw_usage: dict，原始用量数据（当使用独立参数方式时）。
        stage: str，流水线阶段标签。
        request_tokens: int，请求 token 数（独立参数方式）。
        response_tokens: int，响应 token 数（独立参数方式）。
        total_tokens: int，总 token 数（独立参数方式）。
        token_source: str，token 来源类型（独立参数方式）。
    返回:
        ModelInvocationLog 实例，新创建的日志记录。
    """
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
