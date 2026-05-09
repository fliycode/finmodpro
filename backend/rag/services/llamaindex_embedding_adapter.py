from pydantic import ConfigDict, Field

from llama_index.core.embeddings import BaseEmbedding

from llm.services.runtime_service import get_embedding_provider


class LiteLLMEmbeddingAdapter(BaseEmbedding):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    provider: object | None = Field(default=None, exclude=True)
    model_name: str = "finmodpro-litellm-embedding"

    @classmethod
    def class_name(cls) -> str:
        return "finmodpro_litellm_embedding"

    def _resolve_provider(self):
        provider = self.provider
        if provider is None:
            provider = get_embedding_provider()
            object.__setattr__(self, "provider", provider)
        return provider

    def _get_query_embedding(self, query: str) -> list[float]:
        return self._resolve_provider().embed(texts=[query])[0]

    async def _aget_query_embedding(self, query: str) -> list[float]:
        return self._get_query_embedding(query)

    def _get_text_embedding(self, text: str) -> list[float]:
        return self._resolve_provider().embed(texts=[text])[0]

    def _get_text_embeddings(self, texts: list[str]) -> list[list[float]]:
        return self._resolve_provider().embed(texts=texts)
