"""
LlamaIndex 向量存储服务 —— 管理与 Milvus 向量数据库的交互。
类比 SpringBoot: 相当于 @Repository + @Service 的混合层，
封装了 Milvus 连接、向量检索、BM25 检索、混合检索 (hybrid search)
和 MySQL 全文检索等数据访问逻辑。

核心功能:
- 构建/管理 MilvusVectorStore 和 VectorStoreIndex
- 文档的同步、删除和存储清空
- BM25 关键词检索（带 TTL 缓存）
- Milvus 原生混合检索（稠密向量 + 稀疏 BM25）
- MySQL 全文检索（FULLTEXT INDEX）
- 多种检索结果的融合排序（RRF 算法）
"""

import copy
import logging
import threading
import time

from django.conf import settings

from llama_index.core import StorageContext, VectorStoreIndex
from llama_index.core.schema import TextNode
from llama_index.core.vector_stores.types import (
    FilterOperator,
    MetadataFilter,
    MetadataFilters,
)
from llama_index.vector_stores.milvus import MilvusVectorStore

from knowledgebase.models import DocumentChunk
from llm.services.runtime_service import provider_runtime_options
from rag.services.llamaindex_embedding_adapter import FinModProEmbeddingAdapter

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# BM25 retriever cache (thread-safe, TTL-based)
# ---------------------------------------------------------------------------

# 用于保护 BM25 缓存读写操作的线程锁
_bm25_cache_lock = threading.Lock()
# BM25 缓存字典，存储 retriever 实例和构建时间戳
_bm25_cache = {"retriever": None, "built_at": 0.0}


def invalidate_bm25_cache():
    """
    使 BM25 缓存失效，强制下次检索时重新构建 BM25 retriever。

    通常在文档索引更新后调用，确保 BM25 检索使用最新的文档数据。
    类比 SpringBoot: 相当于 @CacheEvict 使缓存失效。
    """
    with _bm25_cache_lock:
        _bm25_cache["retriever"] = None
        _bm25_cache["built_at"] = 0.0


def _build_milvus_vector_store():
    """
    构建 Milvus 向量存储实例。

    返回:
        MilvusVectorStore: 配置好的 Milvus 向量存储连接。
        类比 SpringBoot: 相当于 @Bean 方法创建数据库连接池。
    """
    kwargs = {
        "uri": settings.MILVUS_URI,
        "collection_name": settings.MILVUS_COLLECTION_NAME,
        "dim": settings.KB_EMBEDDING_DIMENSION,
        "embedding_field": "vector",
        "text_key": "content",
        "similarity_metric": "COSINE",
        "overwrite": False,
    }
    token = getattr(settings, "MILVUS_TOKEN", "")
    if token:
        kwargs["token"] = token
    return MilvusVectorStore(**kwargs)


def _build_embed_model():
    """
    构建嵌入模型实例。

    返回:
        FinModProEmbeddingAdapter: 带缓存的嵌入适配器。
    """
    return FinModProEmbeddingAdapter()


def _build_index():
    """
    构建 LlamaIndex 的 VectorStoreIndex 实例。

    返回:
        VectorStoreIndex: 基于 Milvus 向量存储的索引对象。
    """
    vector_store = _build_milvus_vector_store()
    storage_context = StorageContext.from_defaults(vector_store=vector_store)
    return VectorStoreIndex(
        nodes=[],
        storage_context=storage_context,
        embed_model=_build_embed_model(),
    )


def _build_filter_expression(filters):
    """
    将 Python 字典过滤条件转换为 Milvus 标量过滤表达式字符串。

    类比 SpringBoot: 相当于将 @Query 注解中的条件转换为 SQL WHERE 子句。

    参数:
        filters (dict): 过滤条件字典，支持 document_id, doc_type,
                        source_date_from, source_date_to 四个字段。

    返回:
        str | None: Milvus 过滤表达式，如 'document_id == 1 and doc_type == "report"'。
                    无有效过滤条件时返回 None。
    """
    filters = filters or {}
    clauses = []

    document_id = filters.get("document_id")
    if document_id not in (None, ""):
        clauses.append(f"document_id == {int(document_id)}")

    doc_type = filters.get("doc_type")
    if doc_type:
        clauses.append(f'doc_type == "{doc_type}"')

    source_date_from = filters.get("source_date_from")
    if source_date_from:
        clauses.append(f'source_date >= "{source_date_from}"')

    source_date_to = filters.get("source_date_to")
    if source_date_to:
        clauses.append(f'source_date <= "{source_date_to}"')

    return " and ".join(clauses) if clauses else None


def _build_node_id(chunk_id):
    """
    根据 chunk ID 构造 LlamaIndex 节点 ID。

    参数:
        chunk_id: 文档块的整数 ID。

    返回:
        str: 格式为 "chunk:{id}" 的节点 ID 字符串。
    """
    return f"chunk:{int(chunk_id)}"


def _build_chunk_node(chunk):
    """
    将 Django DocumentChunk 模型实例转换为 LlamaIndex TextNode。

    参数:
        chunk (DocumentChunk): 文档块 Django 模型实例。

    返回:
        TextNode: 包含 id、text 和完整元数据的 LlamaIndex 文本节点。
    """
    metadata = chunk.metadata or {}
    document = chunk.document
    return TextNode(
        id_=_build_node_id(chunk.id),
        text=chunk.search_text or chunk.content,
        metadata={
            "document_id": document.id,
            "chunk_id": chunk.id,
            "document_title": metadata.get("document_title") or document.title,
            "doc_type": metadata.get("doc_type") or document.doc_type,
            "source_date": metadata.get("source_date")
            or (document.source_date.isoformat() if document.source_date else None),
            "page_label": metadata.get(
                "page_label", f"chunk-{chunk.chunk_index + 1}"
            ),
            "chunk_index": chunk.chunk_index,
            "window": metadata.get("window", ""),
        },
    )


def _serialize_chunk_result(chunk, score):
    """
    将 DocumentChunk 和相似度分数序列化为前端可用的字典格式。

    参数:
        chunk (DocumentChunk): 文档块实例。
        score (float): 相似度 / 相关性分数。

    返回:
        dict: 包含 document_id, chunk_id, snippet, score 等字段的字典。
    """
    metadata = chunk.metadata or {}
    return {
        "document_id": chunk.document_id,
        "chunk_id": chunk.id,
        "section_chunk_id": chunk.section_chunk_id,
        "document_title": metadata.get("document_title") or chunk.document.title,
        "doc_type": metadata.get("doc_type") or chunk.document.doc_type,
        "source_date": metadata.get("source_date")
        or (chunk.document.source_date.isoformat() if chunk.document.source_date else None),
        "page_label": metadata.get("page_label", f"chunk-{chunk.chunk_index + 1}"),
        "snippet": chunk.content,
        "window": metadata.get("window", ""),
        "metadata": metadata,
        "section_context_summary": None,
        "score": score,
        "vector_score": score,
        "keyword_score": 0.0,
        "matched_queries": [],
    }


def sync_document(document):
    """
    同步（索引）单个文档到 Milvus 向量存储中。

    参数:
        document: Django Document 模型实例，将被拆分为 chunk 后写入 Milvus。

    副作用:
        索引完成后会使 BM25 缓存失效。
    """
    from knowledgebase.services.vector_service import VectorService

    VectorService().index(document)
    invalidate_bm25_cache()


def delete_document(*, document_id, chunk_ids=None):
    """
    从 Milvus 向量存储中删除指定文档的所有 chunk。

    参数:
        document_id (int): 要删除的文档 ID。
        chunk_ids (list[int] | None, 可选): 指定要删除的 chunk ID 列表；
                                            为 None 时删除该文档的所有 chunk。

    副作用:
        删除完成后会使 BM25 缓存失效。
    """
    resolved_chunk_ids = [int(chunk_id) for chunk_id in (chunk_ids or [])]
    if not resolved_chunk_ids:
        resolved_chunk_ids = list(
            DocumentChunk.objects.filter(document_id=document_id).values_list(
                "id", flat=True
            )
        )
    if not resolved_chunk_ids:
        return

    try:
        vector_store = _build_milvus_vector_store()
        for chunk_id in resolved_chunk_ids:
            vector_store.delete(str(chunk_id))
    except Exception:
        logger.exception("failed to delete llamaindex nodes for document %s", document_id)
    invalidate_bm25_cache()


def clear_store():
    """
    清空整个 Milvus 向量存储（删除 collection 中的所有数据）。

    副作用:
        清空后会使 BM25 缓存失效。
    """
    try:
        vector_store = _build_milvus_vector_store()
        vector_store.clear()
    except Exception:
        logger.exception("failed to clear llamaindex milvus store")
    invalidate_bm25_cache()


# ---------------------------------------------------------------------------
# BM25 retrieval
# ---------------------------------------------------------------------------


def _build_bm25_retriever_from_db():
    """
    从数据库中读取所有 search_text 非空的 DocumentChunk，
    构建 LlamaIndex BM25Retriever 实例。

    返回:
        BM25Retriever | None: 构建成功的 BM25 检索器，无数据时返回 None。
    """
    from llama_index.retrievers.bm25 import BM25Retriever

    chunks = list(
        DocumentChunk.objects.select_related("document")
        .exclude(search_text="")
        .iterator(chunk_size=1000)
    )
    if not chunks:
        return None

    nodes = []
    for chunk in chunks:
        node = _build_chunk_node(chunk)
        nodes.append(node)

    language = getattr(settings, "RAG_BM25_LANGUAGE", "zh")
    return BM25Retriever(
        nodes=nodes,
        similarity_top_k=20,
        language=language,
        verbose=False,
    )


def _get_or_build_bm25_retriever():
    """
    获取或构建 BM25 检索器（带 TTL 缓存）。

    返回:
        BM25Retriever | None: 缓存的或新构建的 BM25 检索器实例。
    """
    cache_ttl = max(int(getattr(settings, "RAG_BM25_CACHE_TTL", 600) or 600), 60)
    now = time.monotonic()

    with _bm25_cache_lock:
        cached = _bm25_cache
        if cached["retriever"] is not None and (now - cached["built_at"]) < cache_ttl:
            return cached["retriever"]

    retriever = _build_bm25_retriever_from_db()
    if retriever is None:
        return None

    with _bm25_cache_lock:
        _bm25_cache["retriever"] = retriever
        _bm25_cache["built_at"] = time.monotonic()

    return retriever


def _build_bm25_metadata_filters(filters):
    """
    将 Python 字典过滤条件转换为 BM25 检索器支持的 MetadataFilters 格式。

    参数:
        filters (dict): 过滤条件字典。

    返回:
        MetadataFilters | None: LlamaIndex 格式的元数据过滤集合。
    """
    if not filters:
        return None

    metadata_filters = []

    document_id = filters.get("document_id")
    if document_id not in (None, ""):
        metadata_filters.append(
            MetadataFilter(key="document_id", value=int(document_id), operator=FilterOperator.EQ)
        )

    doc_type = filters.get("doc_type")
    if doc_type:
        metadata_filters.append(
            MetadataFilter(key="doc_type", value=doc_type, operator=FilterOperator.EQ)
        )

    source_date_from = filters.get("source_date_from")
    if source_date_from:
        metadata_filters.append(
            MetadataFilter(key="source_date", value=source_date_from, operator=FilterOperator.GTE)
        )

    source_date_to = filters.get("source_date_to")
    if source_date_to:
        metadata_filters.append(
            MetadataFilter(key="source_date", value=source_date_to, operator=FilterOperator.LTE)
        )

    if not metadata_filters:
        return None
    return MetadataFilters(filters=metadata_filters)


def _serialize_bm25_results(nodes):
    """
    将 BM25 检索返回的节点列表序列化为前端友好的字典列表。

    参数:
        nodes (list): LlamaIndex BM25 检索返回的 NodeWithScore 列表。

    返回:
        list[dict]: 序列化后的检索结果列表，每项包含 document_id, snippet, score 等字段。
    """
    if not nodes:
        return []

    score_by_chunk_id = {}
    for node_with_score in nodes:
        metadata = node_with_score.node.metadata or {}
        chunk_id = metadata.get("chunk_id")
        if chunk_id in (None, ""):
            continue
        score_by_chunk_id[int(chunk_id)] = max(
            score_by_chunk_id.get(int(chunk_id), 0.0),
            float(node_with_score.score or 0.0),
        )

    if not score_by_chunk_id:
        return []

    chunks_by_id = {
        chunk.id: chunk
        for chunk in DocumentChunk.objects.select_related("document").filter(
            id__in=score_by_chunk_id.keys()
        )
    }
    results = []
    for chunk_id, score in score_by_chunk_id.items():
        chunk = chunks_by_id.get(chunk_id)
        if chunk is None:
            continue
        metadata = chunk.metadata or {}
        results.append({
            "document_id": chunk.document_id,
            "chunk_id": chunk.id,
            "section_chunk_id": chunk.section_chunk_id,
            "document_title": metadata.get("document_title") or chunk.document.title,
            "doc_type": metadata.get("doc_type") or chunk.document.doc_type,
            "source_date": metadata.get("source_date")
            or (chunk.document.source_date.isoformat() if chunk.document.source_date else None),
            "page_label": metadata.get("page_label", f"chunk-{chunk.chunk_index + 1}"),
            "snippet": chunk.content,
            "window": metadata.get("window", ""),
            "metadata": metadata,
            "section_context_summary": None,
            "score": score,
            "vector_score": 0.0,
            "keyword_score": score,
            "matched_queries": [],
        })
    return results


def _bm25_search(query, filters=None, limit=5):
    """
    执行 BM25 关键词检索。

    参数:
        query (str): 查询文本。
        filters (dict, 可选): 过滤条件字典。
        limit (int, 可选): 返回结果上限，默认 5。

    返回:
        list[dict]: 按 BM25 分数排序的检索结果列表。
    """
    if not getattr(settings, "RAG_BM25_ENABLED", False):
        return []

    retriever = _get_or_build_bm25_retriever()
    if retriever is None:
        return []

    retriever_copy = copy.copy(retriever)
    # BM25Retriever 存文档在 corpus 而非 _nodes
    corpus = getattr(retriever_copy, "corpus", None) or []
    node_count = len(corpus)
    requested_k = max(int(limit), 1)
    if node_count > 0 and requested_k > node_count:
        requested_k = node_count
    retriever_copy.similarity_top_k = requested_k

    metadata_filters = _build_bm25_metadata_filters(filters)
    if metadata_filters:
        retriever_copy.filters = metadata_filters

    nodes = retriever_copy.retrieve(query)
    return _serialize_bm25_results(nodes)


# ---------------------------------------------------------------------------
# Milvus native hybrid search (dense + sparse BM25)
# ---------------------------------------------------------------------------

# 混合搜索的 Milvus 客户端单例
_hybrid_client = None
# 保护客户端初始化的线程锁
_hybrid_client_lock = threading.Lock()


def _get_hybrid_milvus_client():
    """
    获取 Milvus 原生客户端（线程安全的单例模式）。

    返回:
        MilvusClient: Milvus 原生客户端实例，用于执行 hybrid_search。
    """
    global _hybrid_client
    if _hybrid_client is not None:
        return _hybrid_client
    with _hybrid_client_lock:
        if _hybrid_client is not None:
            return _hybrid_client
        from knowledgebase.services.vector_service import VectorService
        _hybrid_client = VectorService()._get_client()
        return _hybrid_client


def _hybrid_search(*, query, filters=None, top_k=5):
    """
    执行 Milvus 原生混合检索（稠密向量检索 + 稀疏 BM25 检索），
    使用 RRF (Reciprocal Rank Fusion) 算法融合两种检索结果。

    参数:
        query (str): 查询文本。
        filters (dict, 可选): 过滤条件字典。
        top_k (int, 可选): 返回结果数量，默认 5。

    返回:
        list[dict]: 混合检索后的结果列表，按 RRF 分数排序。
    """
    from pymilvus import AnnSearchRequest, RRFRanker

    client = _get_hybrid_milvus_client()
    filter_expr = _build_filter_expression(filters)
    embed_model = _build_embed_model()
    query_vector = embed_model._get_query_embedding(query)

    dense_req = AnnSearchRequest(
        data=[query_vector],
        anns_field="vector",
        param={"metric_type": "COSINE", "params": {}},
        limit=max(int(top_k), 1),
        expr=filter_expr or None,
    )

    sparse_req = AnnSearchRequest(
        data=[query],
        anns_field="sparse_vector",
        param={"metric_type": "BM25"},
        limit=max(int(top_k), 1),
        expr=filter_expr or None,
    )

    rrf_k = max(int(getattr(settings, "RAG_RRF_K", 60) or 60), 1)
    ranker = RRFRanker(rrf_k)

    results = client.hybrid_search(
        collection_name=settings.MILVUS_COLLECTION_NAME,
        reqs=[dense_req, sparse_req],
        ranker=ranker,
        limit=max(int(top_k), 1),
        output_fields=[
            "document_id", "chunk_id", "document_title", "doc_type",
            "source_date", "page_label", "chunk_index", "content",
        ],
    )

    if not results or not results[0]:
        return []

    chunk_ids = []
    score_map = {}
    for hit in results[0]:
        entity = hit.get("entity", {})
        chunk_id = entity.get("chunk_id")
        if chunk_id is None:
            continue
        chunk_ids.append(int(chunk_id))
        score_map[int(chunk_id)] = float(hit.get("distance", 0.0))

    if not chunk_ids:
        return []

    chunks_by_id = {
        chunk.id: chunk
        for chunk in DocumentChunk.objects.select_related("document").filter(id__in=chunk_ids)
    }

    serialized = []
    for chunk_id in chunk_ids:
        chunk = chunks_by_id.get(chunk_id)
        if chunk is None:
            continue
        metadata = chunk.metadata or {}
        serialized.append({
            "document_id": chunk.document_id,
            "chunk_id": chunk.id,
            "section_chunk_id": chunk.section_chunk_id,
            "document_title": metadata.get("document_title") or chunk.document.title,
            "doc_type": metadata.get("doc_type") or chunk.document.doc_type,
            "source_date": metadata.get("source_date")
            or (chunk.document.source_date.isoformat() if chunk.document.source_date else None),
            "page_label": metadata.get("page_label", f"chunk-{chunk.chunk_index + 1}"),
            "snippet": chunk.content,
            "window": metadata.get("window", ""),
            "metadata": metadata,
            "section_context_summary": None,
            "score": score_map.get(chunk_id, 0.0),
            "vector_score": 0.0,
            "keyword_score": 0.0,
            "matched_queries": [],
        })
    return serialized


def search(*, query, filters=None, top_k=5):
    """
    执行 LlamaIndex 向量检索（非混合模式）。

    参数:
        query (str): 查询文本。
        filters (dict, 可选): 过滤条件字典。
        top_k (int, 可选): 返回结果数量，默认 5。

    返回:
        list[dict]: 按向量相似度分数排序的检索结果列表。
    """
    if getattr(settings, "RAG_HYBRID_SEARCH_ENABLED", False):
        return _hybrid_search(query=query, filters=filters, top_k=top_k)

    index = _build_index()
    filter_expr = _build_filter_expression(filters)

    retriever_kwargs = {"similarity_top_k": max(int(top_k), 1)}
    if filter_expr:
        retriever_kwargs["vector_store_kwargs"] = {"filter": filter_expr}

    retriever = index.as_retriever(**retriever_kwargs)
    retrieved_nodes = retriever.retrieve(query)

    if not retrieved_nodes:
        return []

    score_by_chunk_id = {}
    for result in retrieved_nodes:
        metadata = result.node.metadata or {}
        chunk_id = metadata.get("chunk_id")
        if chunk_id in (None, ""):
            continue
        score_by_chunk_id[int(chunk_id)] = max(
            score_by_chunk_id.get(int(chunk_id), 0.0),
            float(result.score or 0.0),
        )

    if not score_by_chunk_id:
        return []

    chunks_by_id = {
        chunk.id: chunk
        for chunk in DocumentChunk.objects.select_related("document").filter(
            id__in=score_by_chunk_id.keys()
        )
    }
    results = []
    for chunk_id, score in score_by_chunk_id.items():
        chunk = chunks_by_id.get(chunk_id)
        if chunk is None:
            continue
        row = _serialize_chunk_result(chunk, score)
        results.append(row)

    results.sort(
        key=lambda item: (item.get("score", 0.0), item.get("chunk_id") or 0),
        reverse=True,
    )
    return results[: int(top_k)]


def _candidate_limit(top_k):
    """
    计算候选检索结果的上限数量。

    公式: max(top_k * RAG_RETRIEVAL_CANDIDATE_MULTIPLIER, RAG_RETRIEVAL_CANDIDATE_FLOOR)

    参数:
        top_k (int): 用户请求的结果数量。

    返回:
        int: 候选结果上限，用于多路检索时的中间结果收集。
    """
    normalized_top_k = max(int(top_k), 1)
    multiplier = max(
        int(getattr(settings, "RAG_RETRIEVAL_CANDIDATE_MULTIPLIER", 1) or 1), 1
    )
    floor = max(int(getattr(settings, "RAG_RETRIEVAL_CANDIDATE_FLOOR", 1) or 1), 1)
    return max(normalized_top_k * multiplier, floor)


def _normalize_queries(query, query_variants=None):
    """
    将查询文本和查询变体规范化为去重后的查询列表。

    参数:
        query (str): 原始查询文本。
        query_variants (list[str] | None, 可选): 查询变体列表。

    返回:
        list[str]: 去重、去空白后的查询文本列表。
    """
    seen = set()
    normalized = []
    for candidate in [query, *(query_variants or [])]:
        value = str(candidate or "").strip()
        if not value or value in seen:
            continue
        seen.add(value)
        normalized.append(value)
    return normalized or [str(query or "").strip()]


def _merge_ranked_results(ranked_lists):
    """
    使用 RRF (Reciprocal Rank Fusion) 算法融合多路检索结果。

    参数:
        ranked_lists (list[tuple]): 每个元素为 (来源名称, 查询文本, 结果列表) 的三元组。

    返回:
        list[dict]: 按 RRF 融合分数降序排列的合并结果列表。
    """
    merged = {}
    rrf_k = max(int(getattr(settings, "RAG_RRF_K", 60) or 60), 1)

    for source_name, source_query, results in ranked_lists:
        for rank, result in enumerate(results, start=1):
            key = (result.get("document_id"), result.get("chunk_id"))
            existing = merged.get(key)
            if existing is None:
                existing = {**result, "score": 0.0, "matched_queries": []}
                merged[key] = existing

            existing["score"] += 1.0 / (rrf_k + rank)
            existing["fusion_score"] = existing["score"]
            existing["vector_score"] = max(
                float(existing.get("vector_score") or 0.0),
                float(result.get("vector_score") or 0.0),
            )
            existing["keyword_score"] = max(
                float(existing.get("keyword_score") or 0.0),
                float(result.get("keyword_score") or 0.0),
            )
            if source_query not in existing["matched_queries"]:
                existing["matched_queries"].append(source_query)

    merged_results = list(merged.values())
    merged_results.sort(
        key=lambda item: (
            item["score"],
            item.get("keyword_score", 0.0),
            item.get("vector_score", 0.0),
            item.get("chunk_id") or 0,
        ),
        reverse=True,
    )
    return merged_results


def _mysql_full_text_search(query, filters=None, limit=5):
    """
    使用 MySQL 的 FULLTEXT 索引进行全文检索。

    参数:
        query (str): 查询文本。
        filters (dict, 可选): 过滤条件字典。
        limit (int, 可选): 返回结果数量，默认 5。

    返回:
        list[dict]: 按全文检索相关性分数排序的结果列表。
    """
    if not getattr(settings, "RAG_MYSQL_FULLTEXT_ENABLED", False):
        return []
    from django.db import connection

    if connection.vendor != "mysql":
        return []

    filters = filters or {}
    chunk_table = DocumentChunk._meta.db_table
    document_table = DocumentChunk._meta.get_field("document").related_model._meta.db_table
    where_clauses = [
        "kc.search_text <> ''",
        "MATCH(kc.search_text) AGAINST (%s IN NATURAL LANGUAGE MODE)",
    ]
    params = [query, query]

    document_id = filters.get("document_id")
    if document_id not in (None, ""):
        where_clauses.append("kc.document_id = %s")
        params.append(int(document_id))

    doc_type = filters.get("doc_type")
    if doc_type:
        where_clauses.append("d.doc_type = %s")
        params.append(doc_type)

    source_date_from = filters.get("source_date_from")
    if source_date_from:
        where_clauses.append("d.source_date >= %s")
        params.append(source_date_from)

    source_date_to = filters.get("source_date_to")
    if source_date_to:
        where_clauses.append("d.source_date <= %s")
        params.append(source_date_to)

    params.append(int(limit))

    sql = f"""
        SELECT
            kc.id,
            MATCH(kc.search_text) AGAINST (%s IN NATURAL LANGUAGE MODE) AS lexical_score
        FROM {chunk_table} kc
        INNER JOIN {document_table} d ON d.id = kc.document_id
        WHERE {' AND '.join(where_clauses)}
        ORDER BY lexical_score DESC, kc.id DESC
        LIMIT %s
    """

    try:
        with connection.cursor() as cursor:
            cursor.execute(sql, params)
            rows = cursor.fetchall()
    except Exception:
        logger.exception("mysql full-text retrieval failed")
        return []

    if not rows:
        return []

    from datetime import date as date_type

    score_by_chunk_id = {int(chunk_id): float(score or 0.0) for chunk_id, score in rows}
    chunk_ids = list(score_by_chunk_id.keys())
    chunks_by_id = {
        chunk.id: chunk
        for chunk in DocumentChunk.objects.select_related("document").filter(id__in=chunk_ids)
    }
    results = []
    for chunk_id in chunk_ids:
        chunk = chunks_by_id.get(chunk_id)
        if chunk is None:
            continue
        lexical_score = score_by_chunk_id[chunk_id]
        metadata = chunk.metadata or {}
        results.append({
            "document_id": chunk.document_id,
            "chunk_id": chunk.id,
            "section_chunk_id": chunk.section_chunk_id,
            "document_title": metadata.get("document_title") or chunk.document.title,
            "doc_type": metadata.get("doc_type") or chunk.document.doc_type,
            "source_date": metadata.get("source_date")
            or (chunk.document.source_date.isoformat() if chunk.document.source_date else None),
            "page_label": metadata.get("page_label", f"chunk-{chunk.chunk_index + 1}"),
            "snippet": chunk.content,
            "window": metadata.get("window", ""),
            "metadata": metadata,
            "section_context_summary": None,
            "score": lexical_score,
            "vector_score": 0.0,
            "keyword_score": lexical_score,
            "matched_queries": [],
        })
    return results


def _keyword_match_score(query, chunk):
    """
    计算查询文本与文档块的关键词匹配分数（基于 token 级别的匹配）。

    参数:
        query (str): 查询文本。
        chunk (DocumentChunk): 文档块实例。

    返回:
        float: 关键词匹配分数，范围 [0.0, 2.0]。
               token 匹配得分 + 短语在 content 中出现 +0.5 + 短语在标题中出现 +0.5。
    """
    import re
    import math
    from collections import Counter

    token_pattern = re.compile(r"[\w一-鿿]+", re.UNICODE)
    query_tokens = token_pattern.findall((query or "").lower())
    if not query_tokens:
        return 0.0

    searchable_text = (chunk.search_text or chunk.content or "").lower()
    content_tokens = token_pattern.findall(searchable_text)
    if not content_tokens:
        return 0.0

    unique_query_tokens = set(query_tokens)
    content_token_set = set(content_tokens)
    matched_token_count = sum(1 for token in unique_query_tokens if token in content_token_set)
    if matched_token_count == 0:
        return 0.0

    score = matched_token_count / max(len(unique_query_tokens), 1)
    phrase = " ".join(query_tokens)
    if phrase and phrase in searchable_text:
        score += 0.5
    title = str((chunk.metadata or {}).get("document_title") or chunk.document.title or "").lower()
    if phrase and phrase in title:
        score += 0.5
    return score


def _fallback_keyword_search(query, filters=None, limit=5):
    """
    备用关键词检索 —— 当向量 / BM25 / MySQL 全文检索都无结果时的兜底方案。
    遍历所有 DocumentChunk 进行 token 级别匹配。

    参数:
        query (str): 查询文本。
        filters (dict, 可选): 过滤条件字典。
        limit (int, 可选): 返回结果上限，默认 5。

    返回:
        list[dict]: 按关键词匹配分数排序的结果列表。
    """
    import re

    token_pattern = re.compile(r"[\w一-鿿]+", re.UNICODE)
    query_tokens = token_pattern.findall((query or "").lower())
    if not query_tokens:
        return []
    query_phrase = " ".join(query_tokens)

    def _matches_filters(metadata, filters):
        """
        检查元数据是否满足过滤条件。

        参数:
            metadata (dict): chunk 的元数据字典。
            filters (dict): 过滤条件字典。

        返回:
            bool: 是否通过所有过滤条件。
        """
        if not filters:
            return True
        from datetime import date as date_type

        document_id = filters.get("document_id")
        if document_id is not None and metadata.get("document_id") != int(document_id):
            return False
        doc_type = filters.get("doc_type")
        if doc_type and metadata.get("doc_type") != doc_type:
            return False
        source_date = metadata.get("source_date")
        if source_date and isinstance(source_date, str):
            try:
                source_date = date_type.fromisoformat(source_date)
            except ValueError:
                source_date = None
        source_date_from = filters.get("source_date_from")
        if source_date_from:
            try:
                from_date = date_type.fromisoformat(source_date_from) if isinstance(source_date_from, str) else source_date_from
                if source_date is None or source_date < from_date:
                    return False
            except ValueError:
                pass
        source_date_to = filters.get("source_date_to")
        if source_date_to:
            try:
                to_date = date_type.fromisoformat(source_date_to) if isinstance(source_date_to, str) else source_date_to
                if source_date is None or source_date > to_date:
                    return False
            except ValueError:
                pass
        return True

    results = []
    queryset = (
        DocumentChunk.objects.select_related("document")
        .only(
            "id",
            "document_id",
            "section_chunk_id",
            "content",
            "search_text",
            "metadata",
            "chunk_index",
            "document__title",
            "document__doc_type",
            "document__source_date",
        )
    )
    for chunk in queryset.iterator(chunk_size=500):
        if not _matches_filters(chunk.metadata or {}, filters or {}):
            continue
        keyword_score = _keyword_match_score(query, chunk)
        if keyword_score <= 0:
            continue
        metadata = chunk.metadata or {}
        results.append({
            "document_id": chunk.document_id,
            "chunk_id": chunk.id,
            "section_chunk_id": chunk.section_chunk_id,
            "document_title": metadata.get("document_title") or chunk.document.title,
            "doc_type": metadata.get("doc_type") or chunk.document.doc_type,
            "source_date": metadata.get("source_date")
            or (chunk.document.source_date.isoformat() if chunk.document.source_date else None),
            "page_label": metadata.get("page_label", f"chunk-{chunk.chunk_index + 1}"),
            "snippet": chunk.content,
            "window": metadata.get("window", ""),
            "metadata": metadata,
            "section_context_summary": None,
            "score": keyword_score,
            "vector_score": 0.0,
            "keyword_score": keyword_score,
            "matched_queries": [],
        })
    results.sort(key=lambda item: item["score"], reverse=True)
    return results[: int(limit)]


def _hybrid_query(query, filters=None, top_k=5, query_variants=None):
    """
    混合查询的顶层编排函数 —— 支持单查询和多查询变体的混合检索。

    参数:
        query (str): 原始查询文本。
        filters (dict, 可选): 过滤条件字典。
        top_k (int, 可选): 返回结果数量，默认 5。
        query_variants (list[str] | None, 可选): 查询变体列表。

    返回:
        list[dict]: 混合检索且融合排序后的结果列表。
    """
    candidate_limit = _candidate_limit(top_k)
    queries = _normalize_queries(query, query_variants)

    # 单个查询：直接返回 hybrid search 结果（Milvus RRFRanker 已在 Milvus 内部融合）
    if len(queries) == 1:
        return _hybrid_search(query=queries[0], filters=filters, top_k=top_k)

    # 多个查询变体：分别检索后取每个 chunk 的最高分数
    merged = {}
    for query_text in queries:
        results = _hybrid_search(
            query=query_text,
            filters=filters,
            top_k=candidate_limit,
        )
        for result in results:
            key = (result.get("document_id"), result.get("chunk_id"))
            existing = merged.get(key)
            if existing is None:
                merged[key] = {**result, "matched_queries": [query_text]}
            else:
                existing["score"] = max(existing["score"], result.get("score", 0.0))
                if query_text not in existing["matched_queries"]:
                    existing["matched_queries"].append(query_text)

    fused = sorted(merged.values(), key=lambda x: x["score"], reverse=True)
    return fused[: int(top_k)]


def query_llamaindex_store(
    query,
    filters=None,
    top_k=5,
    query_variants=None,
    allow_keyword_fallback=True,
    provider_options=None,
):
    """
    查询 LlamaIndex 向量存储的顶层入口函数。

    此函数编排了整个检索流程:
    1. 根据配置决定使用混合检索 (hybrid) 还是多路检索 + RRF 融合
    2. 多路检索包含: 向量检索、BM25 检索、MySQL 全文检索
    3. 当以上检索均无结果时，可降级到关键词 token 匹配兜底
    4. 多路结果通过 RRF 算法融合排序

    类比 SpringBoot: 相当于 @Service 中的核心业务方法，
    协调多个 Repository 和外部服务完成一个完整的检索请求。

    参数:
        query (str): 用户查询文本。
        filters (dict, 可选): 过滤条件（document_id, doc_type, source_date 等）。
        top_k (int, 可选): 返回结果数量，默认 5。
        query_variants (list[str] | None, 可选): 查询变体，用于多查询融合。
        allow_keyword_fallback (bool, 可选): 是否允许在无结果时降级到 token 匹配。
        provider_options (dict, 可选): provider 运行时选项。

    返回:
        list[dict]: 融合排序后的检索结果列表，每项包含 document_id, snippet, score 等字段。
    """
    with provider_runtime_options(provider_options):
        if getattr(settings, "RAG_HYBRID_SEARCH_ENABLED", False):
            return _hybrid_query(query, filters=filters, top_k=top_k, query_variants=query_variants)

        candidate_limit = _candidate_limit(top_k)
        queries = _normalize_queries(query, query_variants)
        ranked_lists = []

        for query_text in queries:
            vector_results = search(
                query=query_text,
                filters=filters,
                top_k=candidate_limit,
            )
            if vector_results:
                ranked_lists.append(("llamaindex_vector", query_text, vector_results))

            bm25_results = _bm25_search(
                query_text,
                filters=filters,
                limit=candidate_limit,
            )
            if bm25_results:
                ranked_lists.append(("bm25", query_text, bm25_results))

            mysql_fulltext_results = _mysql_full_text_search(
                query_text,
                filters=filters,
                limit=candidate_limit,
            )
            if mysql_fulltext_results:
                ranked_lists.append(("mysql_fulltext", query_text, mysql_fulltext_results))

            should_run_keyword_fallback = allow_keyword_fallback and not (
                vector_results or bm25_results or mysql_fulltext_results
            )
            if should_run_keyword_fallback:
                fallback_keyword_results = _fallback_keyword_search(
                    query_text,
                    filters=filters,
                    limit=candidate_limit,
                )
                if fallback_keyword_results:
                    ranked_lists.append(("token_keyword", query_text, fallback_keyword_results))

        return _merge_ranked_results(ranked_lists)[: int(top_k)]
