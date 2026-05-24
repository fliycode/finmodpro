"""
DashScope Provider（类比 SpringBoot 中对接阿里云 DashScope API 的 @Service 实现）。

提供：
- DashScopeEmbeddingProvider: Embedding 向量化（继承自 OpenAICompatibleEmbeddingProvider，
  使用 DashScope 兼容模式的 endpoint）
- DashScopeRerankProvider: Rerank 重排序（使用 DashScope 原生 rerank API）

DashScope 是阿里云的模型服务平台，支持 text-embedding 和 text-rerank 等能力。
"""
import json
import logging
import os
import time
from urllib import error, request

from common.exceptions import UpstreamRateLimitError, UpstreamServiceError
from llm.models import ModelInvocationLog
from llm.services.model_invocation_log_service import record_model_invocation
from llm.services.providers.base import BaseRerankProvider, RerankResult, TokenUsage
from llm.services.providers.openai_compatible_provider import OpenAICompatibleEmbeddingProvider


logger = logging.getLogger(__name__)
_DASHSCOPE_API_KEY_ENV_VAR = "DASHSCOPE_API_KEY"

_DASHSCOPE_RERANK_URL = (
    "https://dashscope.aliyuncs.com/api/v1/services/rerank/text-rerank/text-rerank"
)


class DashScopeEmbeddingProvider(OpenAICompatibleEmbeddingProvider):
    """DashScope Embedding Provider。

    继承自 OpenAICompatibleEmbeddingProvider，使用 DashScope 兼容模式 endpoint。
    默认 endpoint 为 https://dashscope.aliyuncs.com/compatible-mode/v1。
    """
    provider_name = "dashscope"

    def __init__(self, *, endpoint, model_name, options=None, model_config=None):
        """初始化 DashScope Embedding Provider。

        参数:
            endpoint: str，API 端点地址（为 None 时使用默认 DashScope 兼容模式地址）。
            model_name: str，模型名称（如 text-embedding-v3）。
            options: dict 或 None，额外选项（如 api_key）。
            model_config: ModelConfig 实例或 None。
        """
        super().__init__(
            endpoint=(endpoint or "https://dashscope.aliyuncs.com/compatible-mode/v1"),
            model_name=model_name,
            options=options,
            model_config=model_config,
        )


class DashScopeRerankProvider(BaseRerankProvider):
    """DashScope Rerank Provider。

    直接调用 DashScope 原生 rerank API（非 OpenAI 兼容格式），
    将查询和候选文档列表发送到 text-rerank 服务进行相关性排序。
    """
    provider_name = "dashscope"

    def __init__(self, *, endpoint, model_name, options=None, model_config=None):
        """初始化 DashScope Rerank Provider。

        参数:
            endpoint: str，API 端点地址。
            model_name: str，模型名称（如 gte-rerank）。
            options: dict 或 None，额外选项（如 api_key）。
            model_config: ModelConfig 实例或 None。
        """
        self.endpoint = endpoint.rstrip("/")
        self.model_name = model_name
        self.options = options or {}
        self.model_config = model_config

    def _resolve_options(self, options=None):
        """解析并合并选项，确保 api_key 存在。

        优先级：传入的 options > 构造时的 options > 环境变量 DASHSCOPE_API_KEY。

        参数:
            options: dict 或 None，调用时传入的覆盖选项。

        返回:
            dict，合并后的选项字典。

        异常:
            UpstreamServiceError: 当 api_key 无法解析时抛出。
        """
        merged_options = {**self.options, **(options or {})}
        api_key = merged_options.get("api_key")
        if not api_key:
            api_key = os.environ.get(_DASHSCOPE_API_KEY_ENV_VAR, "").strip()
        if api_key:
            merged_options["api_key"] = api_key
        if not api_key:
            raise UpstreamServiceError(
                "DashScope API Key 未配置。",
                status_code=502,
                code="llm_provider_auth_failed",
                provider=self.provider_name,
            )
        return merged_options

    def _build_headers(self, api_key):
        """构建 HTTP 请求头。

        参数:
            api_key: str，API Key。

        返回:
            dict，包含 Authorization 和 Content-Type 的请求头字典。
        """
        return {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    def _record_success(self, *, started_at, usage, trace_id="", request_id=""):
        """记录成功的 Rerank 调用日志。

        参数:
            started_at: float，调用开始时的 monotonic 时间戳。
            usage: TokenUsage，Token 用量。
            trace_id: str，链路追踪 ID。
            request_id: str，请求 ID。
        """
        if self.model_config is None or self.model_config.pk is None:
            return
        try:
            record_model_invocation(
                model_config=self.model_config,
                capability="rerank",
                alias=self.model_config.name,
                upstream_model=self.model_name,
                status=ModelInvocationLog.STATUS_SUCCESS,
                latency_ms=int((time.monotonic() - started_at) * 1000),
                usage=usage,
                trace_id=trace_id,
                request_id=request_id,
            )
        except Exception:
            logger.exception("Failed to record successful rerank invocation log")

    def _record_failure(self, *, started_at, exc, trace_id="", request_id=""):
        """记录失败的 Rerank 调用日志。

        参数:
            started_at: float，调用开始时的 monotonic 时间戳。
            exc: Exception，捕获的异常对象（需有 code 和 message 属性）。
            trace_id: str，链路追踪 ID。
            request_id: str，请求 ID。
        """
        if self.model_config is None or self.model_config.pk is None:
            return
        try:
            record_model_invocation(
                model_config=self.model_config,
                capability="rerank",
                alias=self.model_config.name,
                upstream_model=self.model_name,
                status=ModelInvocationLog.STATUS_FAILED,
                latency_ms=int((time.monotonic() - started_at) * 1000),
                error_code=exc.code,
                error_message=exc.message,
                trace_id=trace_id,
                request_id=request_id,
            )
        except Exception:
            logger.exception("Failed to record failed rerank invocation log")

    def rerank(self, *, query, documents, top_n=None, options=None, trace_id="", request_id=""):
        """对候选文档列表按与查询的相关性进行重排序。

        调用 DashScope text-rerank API，返回按相关性降序排列的文档索引和分数。

        参数:
            query: str，查询文本。
            documents: list[str]，候选文档列表。
            top_n: int 或 None，返回前 N 个结果（None 表示返回全部）。
            options: dict 或 None，调用时覆盖的选项。
            trace_id: str，链路追踪 ID。
            request_id: str，请求 ID。

        返回:
            RerankResult 实例，包含按相关性排序的 items 列表。

        异常:
            UpstreamRateLimitError: 当 API 返回 429 限流时抛出。
            UpstreamServiceError: 当 API 返回错误或网络异常时抛出。
        """
        merged_options = self._resolve_options(options)
        parameters = {"return_documents": False}
        if top_n is not None:
            parameters["top_n"] = top_n
        payload = {
            "model": self.model_name,
            "input": {"query": query, "documents": documents},
            "parameters": parameters,
        }
        started_at = time.monotonic()
        try:
            response = request.urlopen(
                request.Request(
                    _DASHSCOPE_RERANK_URL,
                    data=json.dumps(payload).encode("utf-8"),
                    headers=self._build_headers(merged_options["api_key"]),
                    method="POST",
                ),
                timeout=30,
            )
            response_payload = json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            response_body = exc.read().decode("utf-8", errors="ignore")
            if exc.code == 429:
                mapped = UpstreamRateLimitError(
                    provider=self.provider_name,
                    retry_after=exc.headers.get("Retry-After"),
                )
            elif exc.code in {401, 403} or "api key" in response_body.lower():
                mapped = UpstreamServiceError(
                    "DashScope 认证失败。",
                    status_code=502,
                    code="llm_provider_auth_failed",
                    provider=self.provider_name,
                )
            else:
                mapped = UpstreamServiceError(
                    "模型服务调用失败。",
                    status_code=502,
                    code="llm_provider_error",
                    provider=self.provider_name,
                )
            self._record_failure(
                started_at=started_at,
                exc=mapped,
                trace_id=trace_id,
                request_id=request_id,
            )
            raise mapped from exc
        except (error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            mapped = UpstreamServiceError(
                "DashScope 服务暂不可用。",
                status_code=503,
                code="llm_provider_unavailable",
                provider=self.provider_name,
            )
            self._record_failure(
                started_at=started_at,
                exc=mapped,
                trace_id=trace_id,
                request_id=request_id,
            )
            raise mapped from exc

        output = response_payload.get("output") or {}
        raw_items = output.get("results") or []
        items = [
            {"index": item["index"], "relevance_score": item["relevance_score"]}
            for item in raw_items
            if isinstance(item, dict) and "index" in item and "relevance_score" in item
        ]
        if not items:
            mapped = UpstreamServiceError(
                "模型服务返回了空重排结果。",
                status_code=502,
                code="llm_empty_rerank",
                provider=self.provider_name,
            )
            self._record_failure(
                started_at=started_at,
                exc=mapped,
                trace_id=trace_id,
                request_id=request_id,
            )
            raise mapped
        usage_payload = response_payload.get("usage") or {}
        usage = TokenUsage(
            request_tokens=int(usage_payload.get("input_tokens") or usage_payload.get("prompt_tokens") or 0),
            response_tokens=0,
            total_tokens=int(usage_payload.get("total_tokens") or usage_payload.get("input_tokens") or 0),
            source=(
                ModelInvocationLog.TOKEN_SOURCE_PROVIDER
                if usage_payload
                else ModelInvocationLog.TOKEN_SOURCE_NONE
            ),
            raw=dict(usage_payload),
        )
        result = RerankResult(items=items, usage=usage, raw_response=response_payload)
        self._record_success(
            started_at=started_at,
            usage=usage,
            trace_id=trace_id,
            request_id=request_id,
        )
        return result
