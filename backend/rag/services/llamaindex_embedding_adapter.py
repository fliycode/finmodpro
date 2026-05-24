"""
LlamaIndex Embedding 适配器 —— 将项目自定义的 Embedding Provider 封装为 LlamaIndex 兼容的 Embedding 模型。
类比 SpringBoot: 相当于适配器模式中的 Adapter，将外部 API（DashScope embedding）
适配到 LlamaIndex 框架要求的 BaseEmbedding 接口。

同时内置了基于 Django Cache 的 embedding 缓存，缓存 TTL 为 24 小时。
"""

import asyncio
import hashlib

from django.conf import settings
from django.core.cache import cache
from pydantic import ConfigDict, Field

from llama_index.core.embeddings import BaseEmbedding

from llm.services.runtime_service import get_embedding_provider

# 缓存键前缀，用于在 Redis 中区分 embedding 缓存项
_CACHE_PREFIX = "emb:"
# 缓存过期时间，24 小时（秒）
_CACHE_TTL = 86400  # 24 hours


def _cache_key(text: str, dimension: int) -> str:
    """
    根据文本和向量维度生成唯一的缓存键。

    参数:
        text (str): 需要嵌入的原始文本。
        dimension (int): 嵌入向量的维度（如 1024）。

    返回:
        str: SHA256 哈希后的缓存键，格式为 "emb:{sha256}"。
    """
    raw = f"{dimension}:{text}"
    return _CACHE_PREFIX + hashlib.sha256(raw.encode()).hexdigest()


class FinModProEmbeddingAdapter(BaseEmbedding):
    """
    FinModPro Embedding 适配器，包装项目内置的 embedding provider
    以兼容 LlamaIndex 的 BaseEmbedding 接口。

    类比 SpringBoot: 相当于一个实现了标准接口的 @Component Bean，
    内部委托给实际的外部 API 客户端，并提供缓存层优化。

    属性:
        provider: embedding 提供商实例，延迟加载。
        model_name (str): 模型名称标识。
        dimension (int): 嵌入向量维度，从 settings.KB_EMBEDDING_DIMENSION 读取。
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    provider: object | None = Field(default=None, exclude=True)
    model_name: str = "finmodpro-embedding"
    dimension: int = Field(default=0, exclude=True)

    def model_post_init(self, __context):
        """
        模型初始化后钩子，确保 dimension 有默认值。
        类比 SpringBoot: 相当于 @PostConstruct 初始化方法。
        """
        if self.dimension <= 0:
            object.__setattr__(self, "dimension", settings.KB_EMBEDDING_DIMENSION)

    @classmethod
    def class_name(cls) -> str:
        """返回 LlamaIndex 中使用的类名标识。"""
        return "finmodpro_embedding"

    def _resolve_provider(self):
        """
        解析并缓存 embedding provider 实例（惰性加载）。

        返回:
            object: embedding provider 实例，支持 embed(texts) 方法。
        """
        provider = self.provider
        if provider is None:
            provider = get_embedding_provider()
            object.__setattr__(self, "provider", provider)
        return provider

    def _get_query_embedding(self, query: str) -> list[float]:
        """
        获取单条查询文本的嵌入向量（同步，带缓存）。

        参数:
            query (str): 查询文本。

        返回:
            list[float]: 嵌入向量。
        """
        key = _cache_key(query, self.dimension)
        cached = cache.get(key)
        if cached is not None:
            return cached
        vector = self._resolve_provider().embed(texts=[query]).vectors[0]
        cache.set(key, vector, _CACHE_TTL)
        return vector

    async def _aget_query_embedding(self, query: str) -> list[float]:
        """
        获取单条查询文本的嵌入向量（异步版本），在线程池中执行同步调用。

        参数:
            query (str): 查询文本。

        返回:
            list[float]: 嵌入向量。
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._get_query_embedding, query)

    async def _aget_text_embeddings(self, texts: list[str]) -> list[list[float]]:
        """
        批量获取文本的嵌入向量（异步版本），在线程池中执行同步调用。

        参数:
            texts (list[str]): 文本列表。

        返回:
            list[list[float]]: 嵌入向量列表。
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._get_text_embeddings, texts)

    def _get_text_embedding(self, text: str) -> list[float]:
        """
        获取单条文本的嵌入向量（同步），直接委托给 _get_query_embedding。

        参数:
            text (str): 待嵌入文本。

        返回:
            list[float]: 嵌入向量。
        """
        return self._get_query_embedding(text)

    def _get_text_embeddings(self, texts: list[str]) -> list[list[float]]:
        """
        批量获取文本的嵌入向量（同步，带缓存）。

        参数:
            texts (list[str]): 待嵌入的文本列表。

        返回:
            list[list[float]]: 嵌入向量列表，与输入文本一一对应。
        """
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
