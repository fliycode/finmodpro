"""
项目自定义异常类

定义业务级别的异常类型，每种异常携带语义化的 code + status_code，
由 DRF 异常处理器统一捕获并转换为标准 API 响应格式。

SpringBoot 类比: 自定义 RuntimeException 子类，由 @ControllerAdvice 统一拦截处理。
"""


class UpstreamServiceError(Exception):
    """上游服务异常 — 调用外部 LLM 或第三方服务失败时抛出。

    属性:
        status_code: HTTP 状态码（默认 502 Bad Gateway）
        code: 业务错误码
        provider: 出错的提供商标识
        retry_after: 建议重试等待秒数
    """
    def __init__(self, message, *, status_code=502, code="upstream_error", provider=None, retry_after=None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.code = code
        self.provider = provider
        self.retry_after = retry_after


class ServiceConfigurationError(ValueError):
    """服务配置错误 — 模型或 provider 配置不正确时抛出。"""
    def __init__(self, message, *, code="service_configuration_error", provider=None, details=None):
        super().__init__(message)
        self.message = message
        self.code = code
        self.provider = provider
        self.details = details or {}


class ModelNotConfiguredError(ServiceConfigurationError):
    """模型未配置 — 请求的能力没有对应的启用模型时抛出。

    示例: 系统配置中没有启用 embedding 模型，但请求触发了嵌入操作。
    """
    def __init__(self, capability, message=None):
        resolved_message = message or (
            f"未配置启用的 {capability} 模型。"
        )
        super().__init__(resolved_message, code="model_not_configured", details={"capability": capability})


class ProviderConfigurationError(ServiceConfigurationError):
    """Provider 配置错误 — LLM 提供商的 API Key 等配置缺失或不正确。"""
    def __init__(self, message, *, provider=None, details=None):
        super().__init__(message, code="provider_configuration_error", provider=provider, details=details)


class DuplicateDocumentError(Exception):
    """文档重复异常 — 上传了内容相同（hash 一致）的文档时抛出。"""
    def __init__(self, message, *, existing_document):
        super().__init__(message)
        self.message = message
        self.existing_document = existing_document


class DocumentQualityGateError(ValueError):
    """文档质量检查不通过 — 文档清洗质量分数未达到阈值时抛出。"""
    def __init__(self, message, *, score, quality_gate):
        super().__init__(message)
        self.message = message
        self.score = score
        self.quality_gate = quality_gate


class UpstreamRateLimitError(UpstreamServiceError):
    """上游服务限流异常 — LLM 服务触发限流（HTTP 429）时抛出。"""
    def __init__(self, message="上游模型服务触发限流，请稍后重试。", *, provider=None, retry_after=None):
        super().__init__(message, status_code=429, code="upstream_rate_limited", provider=provider, retry_after=retry_after)
