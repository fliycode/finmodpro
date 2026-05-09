import json
import logging
import time
from urllib import error, request

from common.exceptions import UpstreamRateLimitError, UpstreamServiceError
from llm.models import ModelInvocationLog
from llm.services.model_invocation_log_service import record_model_invocation
from llm.services.providers.base import BaseRerankProvider, RerankResult, TokenUsage
from llm.services.providers.openai_compatible_provider import OpenAICompatibleEmbeddingProvider


logger = logging.getLogger(__name__)

_DASHSCOPE_RERANK_URL = (
    "https://dashscope.aliyuncs.com/api/v1/services/rerank/text-rerank/text-rerank"
)


class DashScopeEmbeddingProvider(OpenAICompatibleEmbeddingProvider):
    provider_name = "dashscope"

    def __init__(self, *, endpoint, model_name, options=None, model_config=None):
        super().__init__(
            endpoint=(endpoint or "https://dashscope.aliyuncs.com/compatible-mode/v1"),
            model_name=model_name,
            options=options,
            model_config=model_config,
        )


class DashScopeRerankProvider(BaseRerankProvider):
    provider_name = "dashscope"

    def __init__(self, *, endpoint, model_name, options=None, model_config=None):
        self.endpoint = endpoint.rstrip("/")
        self.model_name = model_name
        self.options = options or {}
        self.model_config = model_config

    def _resolve_options(self, options=None):
        merged_options = {**self.options, **(options or {})}
        api_key = merged_options.get("api_key")
        if not api_key:
            raise UpstreamServiceError(
                "DashScope API Key 未配置。",
                status_code=502,
                code="llm_provider_auth_failed",
                provider=self.provider_name,
            )
        return merged_options

    def _build_headers(self, api_key):
        return {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    def _record_success(self, *, started_at, usage, trace_id="", request_id=""):
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
