from dataclasses import dataclass, field

from llm.models import ModelInvocationLog


@dataclass(slots=True)
class TokenUsage:
    request_tokens: int = 0
    response_tokens: int = 0
    total_tokens: int = 0
    source: str = ModelInvocationLog.TOKEN_SOURCE_NONE
    raw: dict = field(default_factory=dict)

    def normalized_total(self) -> int:
        return self.total_tokens or (self.request_tokens + self.response_tokens)


@dataclass(slots=True)
class ChatResult:
    content: str
    usage: TokenUsage = field(default_factory=TokenUsage)
    finish_reason: str = ""
    request_id: str = ""
    raw_response: dict = field(default_factory=dict)


@dataclass(slots=True)
class EmbeddingResult:
    vectors: list[list[float]]
    usage: TokenUsage = field(default_factory=TokenUsage)
    request_id: str = ""
    raw_response: dict = field(default_factory=dict)


@dataclass(slots=True)
class RerankResult:
    items: list[dict]
    usage: TokenUsage = field(default_factory=TokenUsage)
    request_id: str = ""
    raw_response: dict = field(default_factory=dict)


class BaseChatProvider:
    def chat(self, *, messages, options=None, trace_id="", request_id=""):
        raise NotImplementedError

    def stream(self, *, messages, options=None):
        raise NotImplementedError


class BaseEmbeddingProvider:
    def embed(self, *, texts, options=None, trace_id="", request_id=""):
        raise NotImplementedError


class BaseRerankProvider:
    def rerank(self, *, query, documents, top_n=None, options=None, trace_id="", request_id=""):
        raise NotImplementedError
