class UpstreamServiceError(Exception):
    def __init__(
        self,
        message,
        *,
        status_code=502,
        code="upstream_error",
        provider=None,
        retry_after=None,
    ):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.code = code
        self.provider = provider
        self.retry_after = retry_after


class ServiceConfigurationError(ValueError):
    def __init__(self, message, *, code="service_configuration_error", provider=None, details=None):
        super().__init__(message)
        self.message = message
        self.code = code
        self.provider = provider
        self.details = details or {}


class ModelNotConfiguredError(ServiceConfigurationError):
    def __init__(self, capability, message=None):
        resolved_message = message or (
            f"\u672a\u914d\u7f6e\u542f\u7528\u4e2d\u7684 {capability} \u6a21\u578b\u3002"
        )
        super().__init__(
            resolved_message,
            code="model_not_configured",
            details={"capability": capability},
        )


class ProviderConfigurationError(ServiceConfigurationError):
    def __init__(self, message, *, provider=None, details=None):
        super().__init__(
            message,
            code="provider_configuration_error",
            provider=provider,
            details=details,
        )


class UpstreamRateLimitError(UpstreamServiceError):
    def __init__(
        self,
        message="上游模型服务触发限流，请稍后重试。",
        *,
        provider=None,
        retry_after=None,
    ):
        super().__init__(
            message,
            status_code=429,
            code="upstream_rate_limited",
            provider=provider,
            retry_after=retry_after,
        )
