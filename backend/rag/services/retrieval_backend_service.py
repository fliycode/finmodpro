"""
RAG 检索后端服务 —— 为不同场景（检索 API / 聊天问答）提供检索入口。
类比 SpringBoot: 相当于 @Service 中的门面层 (Facade)，
为 Controller 层提供简洁的业务方法，屏蔽底层检索实现的复杂性。

两个主要入口:
- retrieve_rag_context: 检索 API 场景（始终允许关键词兜底）
- retrieve_chat_context: 聊天场景（可通过配置关闭关键词兜底）
"""

from rag.services.llamaindex_store_service import query_llamaindex_store


def retrieve_rag_context(*, query, filters=None, top_k=5, query_variants=None):
    """
    为检索 API 场景获取 RAG 上下文。

    始终允许关键词兜底检索（当向量/BM25 检索无结果时，
    降级到 token 级别关键词匹配）。

    参数:
        query (str): 用户查询文本。
        filters (dict, 可选): 过滤条件字典。
        top_k (int, 可选): 返回结果数量，默认 5。
        query_variants (list[str] | None, 可选): 查询变体列表。

    返回:
        list[dict]: 检索结果列表。
    """
    return query_llamaindex_store(
        query=query,
        filters=filters,
        top_k=top_k,
        query_variants=query_variants,
        allow_keyword_fallback=True,
    )


def retrieve_chat_context(*, query, filters=None, top_k=5, query_variants=None):
    """
    为聊天场景获取 RAG 上下文。

    是否允许关键词兜底由 settings.CHAT_RAG_KEYWORD_FALLBACK_ENABLED 配置决定。
    聊天场景对精确性要求更高，因此默认关闭关键词兜底。

    参数:
        query (str): 用户查询文本。
        filters (dict, 可选): 过滤条件字典。
        top_k (int, 可选): 返回结果数量，默认 5。
        query_variants (list[str] | None, 可选): 查询变体列表。

    返回:
        list[dict]: 检索结果列表。
    """
    from django.conf import settings

    allow_keyword_fallback = bool(
        getattr(settings, "CHAT_RAG_KEYWORD_FALLBACK_ENABLED", False)
    )
    return query_llamaindex_store(
        query=query,
        filters=filters,
        top_k=top_k,
        query_variants=query_variants,
        allow_keyword_fallback=allow_keyword_fallback,
    )
