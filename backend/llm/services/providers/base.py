"""
Provider 基类与数据传输对象（类比 SpringBoot 中的接口定义 + DTO 层）。

定义：
- TokenUsage: Token 用量数据类（类比 SpringBoot 中的 @Value 或 DTO）
- ChatResult / EmbeddingResult / RerankResult: 各类能力的结果 DTO
- BaseChatProvider / BaseEmbeddingProvider / BaseRerankProvider: 各能力的抽象基类
  （类比 SpringBoot 中的 Interface，定义子类必须实现的契约方法）

所有具体的供应商 Provider（DeepSeek、DashScope、Ollama 等）都继承自这些基类。
"""
from dataclasses import dataclass, field

from llm.models import ModelInvocationLog


@dataclass(slots=True)
class TokenUsage:
    """Token 用量数据类。

    字段:
        request_tokens: int，请求消耗的 Token 数。
        response_tokens: int，响应消耗的 Token 数。
        total_tokens: int，总 Token 数（可能是供应商直接返回的，不一定等于两者之和）。
        source: str，Token 数据来源标识（provider / calculated / none）。
        raw: dict，供应商返回的原始 usage 数据。
    """
    request_tokens: int = 0
    response_tokens: int = 0
    total_tokens: int = 0
    source: str = ModelInvocationLog.TOKEN_SOURCE_NONE
    raw: dict = field(default_factory=dict)

    def normalized_total(self) -> int:
        """返回规范化的总 Token 数。

        若 total_tokens 有值则直接返回，否则计算 request_tokens + response_tokens。

        返回:
            int，规范化后的总 Token 数。
        """
        return self.total_tokens or (self.request_tokens + self.response_tokens)


@dataclass(slots=True)
class ChatResult:
    """Chat 对话结果 DTO。

    字段:
        content: str，模型返回的文本内容。
        usage: TokenUsage，Token 用量。
        finish_reason: str，结束原因（如 "stop"、"length"）。
        request_id: str，请求 ID（由 API 返回或自动生成）。
        raw_response: dict，供应商返回的原始完整响应。
    """
    content: str
    usage: TokenUsage = field(default_factory=TokenUsage)
    finish_reason: str = ""
    request_id: str = ""
    raw_response: dict = field(default_factory=dict)


@dataclass(slots=True)
class EmbeddingResult:
    """Embedding 向量化结果 DTO。

    字段:
        vectors: list[list[float]]，向量列表（每个元素是一个浮点数列表）。
        usage: TokenUsage，Token 用量。
        request_id: str，请求 ID。
        raw_response: dict，供应商返回的原始完整响应。
    """
    vectors: list[list[float]]
    usage: TokenUsage = field(default_factory=TokenUsage)
    request_id: str = ""
    raw_response: dict = field(default_factory=dict)


@dataclass(slots=True)
class RerankResult:
    """Rerank 重排序结果 DTO。

    字段:
        items: list[dict]，重排序后的文档列表，每项包含 index 和 relevance_score。
        usage: TokenUsage，Token 用量。
        request_id: str，请求 ID。
        raw_response: dict，供应商返回的原始完整响应。
    """
    items: list[dict]
    usage: TokenUsage = field(default_factory=TokenUsage)
    request_id: str = ""
    raw_response: dict = field(default_factory=dict)


class BaseChatProvider:
    """Chat Provider 抽象基类（类比 SpringBoot 中的 Service Interface）。

    所有 Chat Provider 必须实现 chat 和 stream 两个方法。
    """

    def chat(self, *, messages, options=None, trace_id="", request_id=""):
        """发送对话消息并获取完整回复。

        参数:
            messages: list[dict]，对话消息列表，每条包含 role 和 content。
            options: dict 或 None，调用时覆盖的选项（如 temperature、max_tokens）。
            trace_id: str，链路追踪 ID。
            request_id: str，请求唯一 ID。

        返回:
            ChatResult 实例。

        异常:
            NotImplementedError: 子类必须覆盖此方法。
        """
        raise NotImplementedError

    def stream(self, *, messages, options=None):
        """流式发送对话消息并逐块返回回复内容。

        参数:
            messages: list[dict]，对话消息列表。
            options: dict 或 None，调用时覆盖选项。

        Yields:
            str，逐块返回的文本内容。
        """
        raise NotImplementedError


class BaseEmbeddingProvider:
    """Embedding Provider 抽象基类（类比 SpringBoot 中的 Service Interface）。

    所有 Embedding Provider 必须实现 embed 方法。
    """

    def embed(self, *, texts, options=None, trace_id="", request_id=""):
        """将文本列表转换为向量表示。

        参数:
            texts: list[str]，待向量化的文本列表。
            options: dict 或 None，调用时覆盖选项。
            trace_id: str，链路追踪 ID。
            request_id: str，请求唯一 ID。

        返回:
            EmbeddingResult 实例。
        """
        raise NotImplementedError


class BaseRerankProvider:
    """Rerank Provider 抽象基类（类比 SpringBoot 中的 Service Interface）。

    所有 Rerank Provider 必须实现 rerank 方法。
    """

    def rerank(self, *, query, documents, top_n=None, options=None, trace_id="", request_id=""):
        """对候选文档列表按与查询的相关性重新排序。

        参数:
            query: str，查询文本。
            documents: list[str]，候选文档列表。
            top_n: int 或 None，返回 Top-N 结果（None 表示返回全部）。
            options: dict 或 None，调用时覆盖选项。
            trace_id: str，链路追踪 ID。
            request_id: str，请求唯一 ID。

        返回:
            RerankResult 实例。
        """
        raise NotImplementedError
