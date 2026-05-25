"""
OpenAI 兼容 Provider（类比 SpringBoot 中通用的 OpenAI API HTTP Client 封装）。

提供三个能力实现：
- OpenAICompatibleChatProvider: 对话（含 chat 和 stream）
- OpenAICompatibleEmbeddingProvider: 向量嵌入
- OpenAICompatibleRerankProvider: 重排序

三者共享 OpenAICompatibleApiMixin 中的通用 HTTP 逻辑：
- API Key 解析（优先 options，其次环境变量）
- 自动重试机制（传输层错误重试 3 次）
- 标准化错误映射（429 限流、401/403 认证失败、404 模型不存在、常规错误）
- Token 用量提取和调用日志记录

DeepSeek、DashScope 的嵌入等均继承自此 Provider。
"""
import json
import logging
import os
import time
from urllib import error, request

from common.exceptions import UpstreamRateLimitError, UpstreamServiceError
from llm.models import ModelInvocationLog
from llm.services.model_invocation_log_service import record_model_invocation
from llm.services.providers.base import (
    BaseChatProvider,
    BaseEmbeddingProvider,
    BaseRerankProvider,
    ChatResult,
    EmbeddingResult,
    RerankResult,
    TokenUsage,
)


logger = logging.getLogger(__name__)
TRANSPORT_RETRY_ATTEMPTS = 3  # 传输层错误的最大重试次数
# 供应商名到环境变量名的映射
_PROVIDER_API_KEY_ENV_VARS = {
    "deepseek": "DEEPSEEK_API_KEY",
    "dashscope": "DASHSCOPE_API_KEY",
    "openai_compatible": "OPENAI_API_KEY",
}


class OpenAICompatibleApiMixin:
    """OpenAI 兼容 API 通用 Mixin 类。

    提供所有 OpenAI 兼容能力共用的：
    - API Key 解析和认证头构建
    - HTTP POST（带自动重试）
    - Token 用量解析
    - 调用成功/失败日志记录

    类比 SpringBoot 中使用 RestTemplate 封装了重试和异常映射的 HTTP Client 父类。

    属性:
        provider_name: str，供应商名称（子类覆盖）。
        endpoint: str，API 服务地址。
        model_name: str，模型名称。
        options: dict，配置项（api_key 等）。
        model_config: ModelConfig 实例或 None。
    """
    provider_name = "openai_compatible"

    def __init__(self, *, endpoint, model_name, options=None, model_config=None):
        self.endpoint = endpoint.rstrip("/")
        self.model_name = model_name
        self.options = options or {}
        self.model_config = model_config

    def _resolve_options(self, options=None):
        """解析 API Key：优先 options.api_key，其次环境变量。

        参数:
            options: dict 或 None，调用级配置覆盖。
        返回:
            dict，合并后的配置。
        异常:
            UpstreamServiceError: 当 API Key 未配置时抛出。
        """
        merged_options = {**self.options, **(options or {})}
        api_key = merged_options.get("api_key")
        if not api_key:
            env_var_name = _PROVIDER_API_KEY_ENV_VARS.get(self.provider_name)
            if env_var_name:
                api_key = os.environ.get(env_var_name, "").strip()
        if api_key:
            merged_options["api_key"] = api_key
        if not api_key:
            raise UpstreamServiceError(
                "模型 API Key 未配置。",
                status_code=502,
                code="llm_provider_auth_failed",
                provider=self.provider_name,
            )
        return merged_options

    def _api_base(self):
        """获取 API 基地址（自动追加 /v1）。

        返回:
            str，API 基地址 URL。
        """
        if self.endpoint.endswith("/v1"):
            return self.endpoint
        return f"{self.endpoint}/v1"

    def _resolve_timeout_seconds(self, resolved_options):
        """解析超时秒数。

        参数:
            resolved_options: dict，已解析的配置。
        返回:
            int，超时秒数。
        """
        try:
            return max(1, int(resolved_options.get("timeout_seconds") or 30))
        except (TypeError, ValueError):
            return 30

    def _resolve_retry_attempts(self, resolved_options):
        """解析重试次数。

        参数:
            resolved_options: dict，已解析的配置。
        返回:
            int，重试次数。
        """
        try:
            return max(1, int(resolved_options.get("transport_retry_attempts") or TRANSPORT_RETRY_ATTEMPTS))
        except (TypeError, ValueError):
            return TRANSPORT_RETRY_ATTEMPTS

    def _build_url(self, path):
        """拼接完整的 API URL。

        当 options.no_v1_suffix 为 True 时，直接使用 endpoint 作为基地址，
        不追加 /v1 后缀。适用于代理网关等非标准 API 路径场景。

        参数:
            path: str，API 路径（如 '/chat/completions'）。
        返回:
            str，完整 URL。
        """
        if self.options.get("no_v1_suffix"):
            return f"{self.endpoint}{path}"
        return f"{self._api_base()}{path}"

    def _build_headers(self, api_key):
        """构建带认证的 HTTP 请求头。

        参数:
            api_key: str，API Key。
        返回:
            dict，包含 Authorization 和 Content-Type。
        """
        return {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    def _usage_from_payload(self, payload) -> TokenUsage:
        """从 OpenAI 兼容或 Ollama 格式的响应中提取 Token 用量。

        兼容两种格式：
        - OpenAI: usage.prompt_tokens / usage.completion_tokens
        - Ollama: 顶层的 prompt_eval_count / eval_count

        参数:
            payload: dict，API JSON 响应。
        返回:
            TokenUsage，填充了用量信息。
        """
        usage = (payload or {}).get("usage") or {}
        request_tokens = int(usage.get("prompt_tokens") or usage.get("input_tokens") or payload.get("prompt_eval_count") or 0)
        response_tokens = int(usage.get("completion_tokens") or usage.get("output_tokens") or payload.get("eval_count") or 0)
        total_tokens = int(usage.get("total_tokens") or payload.get("total_tokens") or (request_tokens + response_tokens))
        source = (
            ModelInvocationLog.TOKEN_SOURCE_PROVIDER
            if (request_tokens or response_tokens or total_tokens)
            else ModelInvocationLog.TOKEN_SOURCE_NONE
        )
        raw = dict(usage) if usage else {
            "prompt_eval_count": payload.get("prompt_eval_count"),
            "eval_count": payload.get("eval_count"),
        }
        return TokenUsage(
            request_tokens=request_tokens,
            response_tokens=response_tokens,
            total_tokens=total_tokens,
            source=source,
            raw=raw,
        )

    def _record_success(self, *, capability, started_at, usage, trace_id="", request_id="", provider_request_id=""):
        """记录成功调用的日志。

        参数:
            capability: str，能力类型。
            started_at: float，调用开始时间。
            usage: TokenUsage，用量统计。
            trace_id: str，链路追踪 ID。
            request_id: str，请求 ID。
            provider_request_id: str，供应商返回的请求 ID。
        """
        if self.model_config is None or self.model_config.pk is None:
            return
        try:
            record_model_invocation(
                model_config=self.model_config,
                capability=capability,
                alias=self.model_config.name,
                upstream_model=self.model_name,
                status=ModelInvocationLog.STATUS_SUCCESS,
                latency_ms=int((time.monotonic() - started_at) * 1000),
                usage=usage,
                trace_id=trace_id,
                request_id=request_id,
                provider_request_id=provider_request_id,
            )
        except Exception:
            logger.exception("Failed to record successful %s invocation log", capability)

    def _record_failure(self, *, capability, started_at, exc, trace_id="", request_id=""):
        """记录失败调用的日志。

        参数:
            capability: str，能力类型。
            started_at: float，调用开始时间。
            exc: 异常对象。
            trace_id: str，链路追踪 ID。
            request_id: str，请求 ID。
        """
        if self.model_config is None or self.model_config.pk is None:
            return
        try:
            record_model_invocation(
                model_config=self.model_config,
                capability=capability,
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
            logger.exception("Failed to record failed %s invocation log", capability)

    def _post_json(self, path, payload, *, options=None, capability):
        """向 OpenAI 兼容 API 发送 JSON POST 请求（带自动重试）。

        对 HTTPError 进行分类映射：
        - 429 -> UpstreamRateLimitError
        - 401/403 或含 "api key"/"unauthorized" -> 认证失败
        - 404 或含 "model not" -> 模型名称无效
        - 其他 -> 通用服务错误
        - 传输错误（URLError/TimeoutError）重试最多 retry_attempts 次

        参数:
            path: str，API 路径。
            payload: dict，请求体。
            options: dict 或 None，调用级选项。
            capability: str，能力类型（用于日志）。

        返回:
            dict，解析后的 JSON 响应。
        """
        resolved_options = self._resolve_options(options)
        timeout_seconds = self._resolve_timeout_seconds(resolved_options)
        retry_attempts = self._resolve_retry_attempts(resolved_options)
        body = json.dumps(payload).encode("utf-8")
        url = self._build_url(path)
        logger.info(
            "Calling %s provider",
            self.provider_name,
            extra={
                "provider": self.provider_name,
                "capability": capability,
                "model_name": self.model_name,
                "url": url,
            },
        )
        for attempt in range(1, retry_attempts + 1):
            try:
                response = request.urlopen(
                    request.Request(url, data=body, headers=self._build_headers(resolved_options["api_key"]), method="POST"),
                    timeout=timeout_seconds,
                )
                return json.loads(response.read().decode("utf-8"))
            except error.HTTPError as exc:
                response_body = exc.read().decode("utf-8", errors="ignore")
                logger.exception(
                    "HTTP error from %s provider",
                    self.provider_name,
                    extra={
                        "provider": self.provider_name,
                        "capability": capability,
                        "model_name": self.model_name,
                        "status_code": exc.code,
                        "response_body": response_body[:500],
                    },
                )
                lowered_body = response_body.lower()
                if exc.code == 429:
                    raise UpstreamRateLimitError(
                        provider=self.provider_name,
                        retry_after=exc.headers.get("Retry-After"),
                    ) from exc
                if exc.code in {401, 403} or "api key" in lowered_body or "unauthorized" in lowered_body:
                    raise UpstreamServiceError(
                        "模型服务认证失败。",
                        status_code=502,
                        code="llm_provider_auth_failed",
                        provider=self.provider_name,
                    ) from exc
                if exc.code == 404 or ("model" in lowered_body and "not" in lowered_body):
                    raise UpstreamServiceError(
                        "模型名称无效。",
                        status_code=502,
                        code="llm_provider_invalid_model",
                        provider=self.provider_name,
                    ) from exc
                raise UpstreamServiceError(
                    "模型服务调用失败。",
                    status_code=502,
                    code="llm_provider_error",
                    provider=self.provider_name,
                ) from exc
            except (error.URLError, TimeoutError) as exc:
                if attempt < retry_attempts:
                    logger.warning(
                        "Retrying %s provider call after transport error",
                        self.provider_name,
                        extra={
                            "provider": self.provider_name,
                            "capability": capability,
                            "model_name": self.model_name,
                            "attempt": attempt,
                        },
                    )
                    continue
                logger.exception(
                    "Transport error from %s provider",
                    self.provider_name,
                    extra={
                        "provider": self.provider_name,
                        "capability": capability,
                        "model_name": self.model_name,
                    },
                )
                raise UpstreamServiceError(
                    "模型服务暂不可用。",
                    status_code=503,
                    code="llm_provider_unavailable",
                    provider=self.provider_name,
                ) from exc
            except json.JSONDecodeError as exc:
                logger.exception(
                    "JSON decode error from %s provider",
                    self.provider_name,
                    extra={
                        "provider": self.provider_name,
                        "capability": capability,
                        "model_name": self.model_name,
                    },
                )
                raise UpstreamServiceError(
                    "模型服务返回格式非法。",
                    status_code=502,
                    code="llm_provider_invalid_response",
                    provider=self.provider_name,
                ) from exc


class OpenAICompatibleChatProvider(OpenAICompatibleApiMixin, BaseChatProvider):
    """OpenAI 兼容对话 Provider。

    调用 POST /v1/chat/completions，支持 chat 和 stream 两种模式。
    """

    def chat(self, *, messages, options=None, trace_id="", request_id=""):
        """发送对话请求（非流式）。

        参数:
            messages: list[dict]，消息列表（OpenAI Chat 格式）。
            options: dict 或 None，调用级覆盖（temperature、max_tokens、response_format）。
            trace_id: str，链路追踪 ID。
            request_id: str，请求 ID。

        返回:
            ChatResult，包含模型回复、用量和元数据。
        """
        merged_options = self._resolve_options(options)
        chat_path = merged_options.get("chat_path") or "/chat/completions"
        payload = {
            "model": self.model_name,
            "messages": messages,
            "stream": False,
        }
        if merged_options.get("temperature") is not None:
            payload["temperature"] = merged_options["temperature"]
        if merged_options.get("max_tokens") is not None:
            payload["max_tokens"] = merged_options["max_tokens"]
        if merged_options.get("response_format") is not None:
            payload["response_format"] = merged_options["response_format"]
        started_at = time.monotonic()
        try:
            response_payload = self._post_json(
                chat_path,
                payload,
                options=options,
                capability="chat",
            )
        except (UpstreamServiceError, UpstreamRateLimitError) as exc:
            self._record_failure(
                capability="chat",
                started_at=started_at,
                exc=exc,
                trace_id=trace_id,
                request_id=request_id,
            )
            raise
        usage = self._usage_from_payload(response_payload)
        # 兼容两种响应格式：
        # - OpenAI 标准: choices[0].message.content
        # - Ollama 原生: message.content（某些代理会透传 Ollama 原始响应）
        choices = response_payload.get("choices") or []
        if choices:
            first_choice = choices[0] or {}
            message = first_choice.get("message") or {}
            finish_reason = first_choice.get("finish_reason") or ""
        else:
            message = response_payload.get("message") or {}
            finish_reason = response_payload.get("done_reason") or ""
        content = message.get("content")
        if isinstance(content, list):
            content = "".join(str(item) for item in content)
        if not content:
            exc = UpstreamServiceError(
                "模型服务返回了空响应。",
                status_code=502,
                code="llm_empty_response",
                provider=self.provider_name,
            )
            self._record_failure(
                capability="chat",
                started_at=started_at,
                exc=exc,
                trace_id=trace_id,
                request_id=request_id,
            )
            raise exc
        result = ChatResult(
            content=content,
            usage=usage,
            finish_reason=finish_reason,
            request_id=response_payload.get("id") or "",
            raw_response=response_payload,
        )
        self._record_success(
            capability="chat",
            started_at=started_at,
            usage=usage,
            trace_id=trace_id,
            request_id=request_id,
            provider_request_id=result.request_id,
        )
        return result

    def stream(self, *, messages, options=None):
        """流式对话接口（生成器）。

        参数:
            messages: list[dict]，消息列表。
            options: dict 或 None，调用级覆盖选项。

        产出:
            str，每次产出一段文本增量（SSE 格式解析后的 content 字段）。
        """
        merged_options = self._resolve_options(options)
        chat_path = merged_options.get("chat_path") or "/chat/completions"
        payload = {
            "model": self.model_name,
            "messages": messages,
            "stream": True,
        }
        if merged_options.get("temperature") is not None:
            payload["temperature"] = merged_options["temperature"]
        if merged_options.get("max_tokens") is not None:
            payload["max_tokens"] = merged_options["max_tokens"]
        if merged_options.get("response_format") is not None:
            payload["response_format"] = merged_options["response_format"]
        body = json.dumps(payload).encode("utf-8")
        url = self._build_url(chat_path)
        try:
            response = request.urlopen(
                request.Request(
                    url,
                    data=body,
                    headers=self._build_headers(merged_options["api_key"]),
                    method="POST",
                ),
                timeout=self._resolve_timeout_seconds(merged_options),
            )
            for raw_line in response:
                line = raw_line.decode("utf-8", errors="ignore").strip()
                if not line or not line.startswith("data:"):
                    continue
                data = line.removeprefix("data:").strip()
                if data == "[DONE]":
                    break
                try:
                    chunk_payload = json.loads(data)
                except json.JSONDecodeError:
                    continue
                choices = chunk_payload.get("choices") or []
                delta = (choices[0] or {}).get("delta") or {}
                content = delta.get("content")
                if content:
                    yield content
        except error.HTTPError as exc:
            response_body = exc.read().decode("utf-8", errors="ignore").lower()
            if exc.code == 429:
                raise UpstreamRateLimitError(
                    provider=self.provider_name,
                    retry_after=exc.headers.get("Retry-After"),
                ) from exc
            if exc.code in {401, 403} or "api key" in response_body or "unauthorized" in response_body:
                raise UpstreamServiceError(
                    "模型服务认证失败。",
                    status_code=502,
                    code="llm_provider_auth_failed",
                    provider=self.provider_name,
                ) from exc
            raise UpstreamServiceError(
                "模型服务暂不可用。",
                status_code=503,
                code="llm_provider_unavailable",
                provider=self.provider_name,
            ) from exc
        except (error.URLError, TimeoutError) as exc:
            raise UpstreamServiceError(
                "模型服务暂不可用。",
                status_code=503,
                code="llm_provider_unavailable",
                provider=self.provider_name,
            ) from exc


class OpenAICompatibleEmbeddingProvider(OpenAICompatibleApiMixin, BaseEmbeddingProvider):
    """OpenAI 兼容向量嵌入 Provider。

    调用 POST /v1/embeddings，支持 dimensions 和 encoding_format 参数。
    """

    def embed(self, *, texts, options=None, trace_id="", request_id=""):
        """生成文本的向量嵌入。

        参数:
            texts: list[str]，待嵌入的文本列表。
            options: dict 或 None，调用级选项（dimensions、encoding_format）。
            trace_id: str，链路追踪 ID。
            request_id: str，请求 ID。

        返回:
            EmbeddingResult，包含向量列表（按输入 text 顺序排列）、用量和元数据。

        异常:
            UpstreamServiceError: 返回空向量、向量数量不匹配等服务端错误。
        """
        started_at = time.monotonic()
        merged_options = self._resolve_options(options)
        payload = {
            "model": self.model_name,
            "input": texts[0] if len(texts) == 1 else texts,
            "encoding_format": merged_options.get("encoding_format") or "float",
        }
        if "dimensions" in merged_options:
            payload["dimensions"] = int(merged_options["dimensions"])
        try:
            response_payload = self._post_json(
                "/embeddings",
                payload,
                options=options,
                capability="embedding",
            )
        except (UpstreamServiceError, UpstreamRateLimitError) as exc:
            self._record_failure(
                capability="embedding",
                started_at=started_at,
                exc=exc,
                trace_id=trace_id,
                request_id=request_id,
            )
            raise
        data = response_payload.get("data") or []
        vectors = []
        for item in data:
            embedding = (item or {}).get("embedding")
            if not isinstance(embedding, list) or not embedding:
                exc = UpstreamServiceError(
                    "模型服务返回了空向量。",
                    status_code=502,
                    code="llm_empty_embedding",
                    provider=self.provider_name,
                )
                self._record_failure(
                    capability="embedding",
                    started_at=started_at,
                    exc=exc,
                    trace_id=trace_id,
                    request_id=request_id,
                )
                raise exc
            vectors.append(embedding)
        if len(vectors) != len(texts):
            exc = UpstreamServiceError(
                "模型服务返回的向量数量不匹配。",
                status_code=502,
                code="llm_invalid_embedding_count",
                provider=self.provider_name,
            )
            self._record_failure(
                capability="embedding",
                started_at=started_at,
                exc=exc,
                trace_id=trace_id,
                request_id=request_id,
            )
            raise exc
        usage = self._usage_from_payload(response_payload)
        result = EmbeddingResult(
            vectors=vectors,
            usage=usage,
            request_id=response_payload.get("id") or "",
            raw_response=response_payload,
        )
        self._record_success(
            capability="embedding",
            started_at=started_at,
            usage=usage,
            trace_id=trace_id,
            request_id=request_id,
            provider_request_id=result.request_id,
        )
        return result


class OpenAICompatibleRerankProvider(OpenAICompatibleApiMixin, BaseRerankProvider):
    """OpenAI 兼容重排序 Provider。

    调用 POST /v1/rerank，兼容 Jina/Cohere 等供应商的重排 API 格式。
    """

    def rerank(self, *, query, documents, top_n=None, options=None, trace_id="", request_id=""):
        """对文档列表进行重排序。

        参数:
            query: str，查询文本。
            documents: list[str]，待排序的文档列表。
            top_n: int 或 None，返回前 N 个结果。
            options: dict 或 None，调用级选项。
            trace_id: str，链路追踪 ID。
            request_id: str，请求 ID。

        返回:
            RerankResult，包含排序后的 items（index + relevance_score）、用量和元数据。

        异常:
            UpstreamServiceError: 返回空重排结果等服务端错误。
        """
        payload = {
            "model": self.model_name,
            "query": query,
            "documents": documents,
        }
        if top_n is not None:
            payload["top_n"] = top_n
        started_at = time.monotonic()
        try:
            response_payload = self._post_json(
                "/rerank",
                payload,
                options=options,
                capability="rerank",
            )
        except (UpstreamServiceError, UpstreamRateLimitError) as exc:
            self._record_failure(
                capability="rerank",
                started_at=started_at,
                exc=exc,
                trace_id=trace_id,
                request_id=request_id,
            )
            raise
        raw_items = response_payload.get("results") or response_payload.get("data") or []
        items = [
            {
                "index": item["index"],
                "relevance_score": item["relevance_score"],
            }
            for item in raw_items
            if isinstance(item, dict) and "index" in item and "relevance_score" in item
        ]
        if not items:
            exc = UpstreamServiceError(
                "模型服务返回了空重排结果。",
                status_code=502,
                code="llm_empty_rerank",
                provider=self.provider_name,
            )
            self._record_failure(
                capability="rerank",
                started_at=started_at,
                exc=exc,
                trace_id=trace_id,
                request_id=request_id,
            )
            raise exc
        usage = self._usage_from_payload(response_payload)
        result = RerankResult(
            items=items,
            usage=usage,
            request_id=response_payload.get("id") or "",
            raw_response=response_payload,
        )
        self._record_success(
            capability="rerank",
            started_at=started_at,
            usage=usage,
            trace_id=trace_id,
            request_id=request_id,
            provider_request_id=result.request_id,
        )
        return result
