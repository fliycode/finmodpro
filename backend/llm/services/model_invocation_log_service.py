from llm.models import ModelInvocationLog


def record_model_invocation(
    *,
    model_config,
    capability,
    alias,
    upstream_model,
    status,
    latency_ms,
    request_tokens=0,
    response_tokens=0,
    error_code="",
    error_message="",
    trace_id="",
    request_id="",
    stage="",
):
    return ModelInvocationLog.objects.create(
        model_config=model_config,
        capability=capability,
        provider=model_config.provider if model_config is not None else "litellm",
        alias=alias,
        upstream_model=upstream_model,
        status=status,
        latency_ms=latency_ms,
        request_tokens=request_tokens,
        response_tokens=response_tokens,
        error_code=error_code,
        error_message=error_message,
        trace_id=trace_id,
        request_id=request_id,
        stage=stage,
    )
