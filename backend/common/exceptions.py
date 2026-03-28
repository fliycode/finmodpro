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
