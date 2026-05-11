import asyncio
import hashlib

from django.conf import settings
from django.core.cache import cache
from pydantic import ConfigDict, Field

from llama_index.core.embeddings import BaseEmbedding

from llm.services.runtime_service import get_embedding_provider

_CACHE_PREFIX = "emb:"
_CACHE_TTL = 86400  # 24 hours


def _cache_key(text: str, dimension: int) -> str:
    raw = f"{dimension}:{text}"
    return _CACHE_PREFIX + hashlib.sha256(raw.encode()).hexdigest()


class FinModProEmbeddingAdapter(BaseEmbedding):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    provider: object | None = Field(default=None, exclude=True)
    model_name: str = "finmodpro-embedding"
    dimension: int = Field(default=0, exclude=True)

    def model_post_init(self, __context):
        if self.dimension <= 0:
            object.__setattr__(self, "dimension", settings.KB_EMBEDDING_DIMENSION)

    @classmethod
    def class_name(cls) -> str:
        return "finmodpro_embedding"

    def _resolve_provider(self):
        provider = self.provider
        if provider is None:
            provider = get_embedding_provider()
            object.__setattr__(self, "provider", provider)
        return provider

    def _get_query_embedding(self, query: str) -> list[float]:
        key = _cache_key(query, self.dimension)
        cached = cache.get(key)
        if cached is not None:
            return cached
        vector = self._resolve_provider().embed(texts=[query]).vectors[0]
        cache.set(key, vector, _CACHE_TTL)
        return vector

    async def _aget_query_embedding(self, query: str) -> list[float]:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._get_query_embedding, query)

    async def _aget_text_embeddings(self, texts: list[str]) -> list[list[float]]:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._get_text_embeddings, texts)

    def _get_text_embedding(self, text: str) -> list[float]:
        return self._get_query_embedding(text)

    def _get_text_embeddings(self, texts: list[str]) -> list[list[float]]:
        keys = [_cache_key(t, self.dimension) for t in texts]
        cached = cache.get_many(keys)

        results: list[list[float] | None] = [None] * len(texts)
        uncached_indices: list[int] = []

        for i, key in enumerate(keys):
            if key in cached:
                results[i] = cached[key]
            else:
                uncached_indices.append(i)

        if uncached_indices:
            uncached_texts = [texts[i] for i in uncached_indices]
            vectors = self._resolve_provider().embed(texts=uncached_texts).vectors
            to_set: dict[str, list[float]] = {}
            for idx, vector in zip(uncached_indices, vectors):
                results[idx] = vector
                to_set[keys[idx]] = vector
            cache.set_many(to_set, _CACHE_TTL)

        return results  # type: ignore[return-value]
