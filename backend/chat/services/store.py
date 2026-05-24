"""
LangGraph Memory Store 的 Django 实现（DjangoMemoryStore）。

类比 SpringBoot：
  - DjangoMemoryStore 相当于一个自定义的 Repository 实现（或 DAO 层），
    将 LangGraph 的 BaseStore 接口适配到 Django ORM（MemoryItem 模型）。
  - 类似于 Spring Data JPA 中自定义的 JpaRepository 扩展实现。
  - BaseStore 接口定义了 put / get / search / list_namespaces 四个操作，
    分别对应于 CRUD 中的 Create+Update / Read / Search / List。

存储模型：
  - 命名空间（namespace）映射到 Django 的 (user_id, scope_type, scope_key) 三元组。
  - 键（key）映射到 MemoryItem.fingerprint（SHA256 哈希）。
  - 值（value）映射到 MemoryItem 的 title / content / memory_type 等字段。

语义搜索：
  - 当 search() 收到 query 参数时，先通过 embedding_service 将查询文本转为向量，
    再用余弦相似度（cosine similarity）对候选记忆进行排序。
  - 置顶（pinned）记忆额外加 1.0 分。
  - 如果 embedding 计算失败，回退到最近更新排序。
"""

import asyncio
import logging
import math
from typing import Iterable

from langgraph.store.base import BaseStore, GetOp, Item, ListNamespacesOp, Op, PutOp, SearchOp

from chat.models import MemoryItem
from knowledgebase.services.embedding_service import build_dense_embedding

logger = logging.getLogger(__name__)


def _cosine_similarity(vec_a: list, vec_b: list) -> float:
    """
    计算两个浮点向量之间的余弦相似度。

    纯 Python 实现，适用于小批量向量比较场景。

    参数：
      - vec_a: list[float] 向量 A（如查询向量）。
      - vec_b: list[float] 向量 B（如记忆条目的 embedding）。

    返回：
      - float: [-1.0, 1.0] 范围内的余弦相似度。如果任一向量的模为 0，返回 0.0。
    """
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _namespace_to_user_id(namespace: tuple) -> int:
    """
    从 LangGraph 命名空间元组中提取用户 ID。

    LangGraph 命名空间格式：("memories", str(user_id), ...)

    参数：
      - namespace: tuple 如 ("memories", "123", "dataset", "456")。

    返回：
      - int: 用户 ID。
    """
    return int(namespace[1])


def _namespace_to_scope(namespace: tuple) -> tuple:
    """
    将 LangGraph 命名空间元组映射到 (scope_type, scope_key)。

    规则：
      - 长度 >= 4 且第 3 位为 "dataset" -> (SCOPE_DATASET, namespace[3])
      - 否则 -> (SCOPE_USER_GLOBAL, "")

    参数：
      - namespace: tuple LangGraph 命名空间。

    返回：
      - tuple[str, str]: (scope_type, scope_key)。
    """
    if len(namespace) >= 4 and namespace[2] == "dataset":
        return MemoryItem.SCOPE_DATASET, str(namespace[3])
    return MemoryItem.SCOPE_USER_GLOBAL, ""


def _scope_to_namespace(memory: MemoryItem) -> tuple:
    """
    将 MemoryItem 的作用域转换为 LangGraph 命名空间。

    参数：
      - memory: MemoryItem 实例。

    返回：
      - tuple: 对应的命名空间元组，如 ("memories", "123") 或 ("memories", "123", "dataset", "456")。
    """
    base = ("memories", str(memory.user_id))
    if memory.scope_type == MemoryItem.SCOPE_DATASET:
        return base + ("dataset", memory.scope_key)
    return base


def _memory_to_item(memory: MemoryItem) -> Item:
    """
    将 Django MemoryItem 模型实例转换为 LangGraph Item 对象。

    参数：
      - memory: MemoryItem 实例。

    返回：
      - Item: LangGraph Item 对象，包含 namespace / key / value / created_at / updated_at。
    """
    return Item(
        namespace=_scope_to_namespace(memory),
        key=memory.fingerprint,
        value={
            "title": memory.title,
            "content": memory.content,
            "memory_type": memory.memory_type,
            "confidence_score": float(memory.confidence_score),
            "pinned": memory.pinned,
            "source_kind": memory.source_kind,
        },
        created_at=memory.created_at,
        updated_at=memory.updated_at,
    )


class DjangoMemoryStore(BaseStore):
    """
    基于 Django ORM（MemoryItem 模型）实现的 LangGraph BaseStore。

    类比 SpringBoot：
      - 相当于实现了 Spring Data 中自定义 Store 接口的 @Repository Bean。
      - 将 LangGraph 的状态存储操作转化为 Django ORM 的数据库操作。

    支持的操作：
      - put(namespace, key, value): 创建或更新记忆条目
      - get(namespace, key): 按命名空间+键读取单条记忆
      - search(namespace_prefix, query, limit): 语义搜索 + 关键词搜索记忆列表
      - list_namespaces(): 列出所有的命名空间
    """

    def batch(self, ops: Iterable[Op]) -> list:
        """
        批量执行 LangGraph Store 操作（同步版本）。

        参数：
          - ops: Iterable[Op] 操作列表（PutOp / GetOp / SearchOp / ListNamespacesOp）。

        返回：
          - list: 每个操作对应的结果列表。
        """
        results = []
        for op in ops:
            if isinstance(op, PutOp):
                results.append(self._handle_put(op))
            elif isinstance(op, GetOp):
                results.append(self._handle_get(op))
            elif isinstance(op, SearchOp):
                results.append(self._handle_search(op))
            elif isinstance(op, ListNamespacesOp):
                results.append(self._handle_list_namespaces(op))
            else:
                results.append(None)
        return results

    async def abatch(self, ops: Iterable[Op]) -> list:
        """
        批量执行 LangGraph Store 操作（异步版本）。

        在默认事件循环的线程池中执行同步 batch 方法，适用于异步上下文。

        参数：
          - ops: Iterable[Op] 操作列表。

        返回：
          - list: 每个操作对应的结果列表。
        """
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self.batch, list(ops))

    def _handle_put(self, op: PutOp):
        """
        处理 put 操作：写入或更新记忆条目。

        如果 op.value 为 None，则软删除匹配的记忆（status -> deleted）。
        如果内容非空且是新建或缺少 embedding，则计算并保存文本向量。

        参数：
          - op: PutOp 包含 namespace / key / value。

        返回：
          - None（LangGraph Store 规范中 put 操作不返回值）。
        """
        user_id = _namespace_to_user_id(op.namespace)
        scope_type, scope_key = _namespace_to_scope(op.namespace)

        if op.value is None:
            MemoryItem.objects.filter(
                user_id=user_id,
                fingerprint=op.key,
                scope_type=scope_type,
                scope_key=scope_key,
            ).update(status=MemoryItem.STATUS_DELETED)
            return None

        value = op.value
        content = value.get("content", "")
        obj, created = MemoryItem.objects.update_or_create(
            user_id=user_id,
            fingerprint=op.key,
            scope_type=scope_type,
            scope_key=scope_key,
            defaults={
                "title": str(value.get("title", ""))[:255],
                "content": content,
                "memory_type": value.get("memory_type", MemoryItem.TYPE_CONFIRMED_FACT),
                "confidence_score": value.get("confidence_score", 0.0),
                "pinned": value.get("pinned", False),
                "source_kind": value.get("source_kind", MemoryItem.SOURCE_AUTO),
                "status": MemoryItem.STATUS_ACTIVE,
            },
        )
        if content and (created or obj.embedding in (None, [])):
            try:
                vec = build_dense_embedding(content)
                obj.embedding = vec
                obj.save(update_fields=["embedding"])
            except Exception:
                logger.warning("Failed to compute memory embedding", exc_info=True)
        return None

    def _handle_get(self, op: GetOp):
        """
        处理 get 操作：按命名空间 + 键读取单条记忆。

        参数：
          - op: GetOp 包含 namespace / key。

        返回：
          - Item|None: 匹配的 LangGraph Item，不存在时返回 None。
        """
        user_id = _namespace_to_user_id(op.namespace)
        scope_type, scope_key = _namespace_to_scope(op.namespace)
        try:
            memory = MemoryItem.objects.get(
                user_id=user_id,
                fingerprint=op.key,
                scope_type=scope_type,
                scope_key=scope_key,
                status=MemoryItem.STATUS_ACTIVE,
            )
            return _memory_to_item(memory)
        except MemoryItem.DoesNotExist:
            return None

    def _handle_search(self, op: SearchOp) -> list:
        """
        处理 search 操作：在命名空间前缀内搜索记忆。

        搜索策略：
          1. 如果提供了 query，尝试语义搜索（embedding + cosine similarity）
          2. 置顶记忆额外加 1.0 分
          3. 语义搜索失败时回退到数据库排序（置顶优先 + 最近更新）

        参数：
          - op: SearchOp 包含 namespace_prefix / query / limit / offset。

        返回：
          - list[Item]: 匹配的 LangGraph Item 列表。
        """
        prefix = op.namespace_prefix
        if len(prefix) < 2:
            return []

        user_id = int(prefix[1])
        queryset = MemoryItem.objects.filter(
            user_id=user_id,
            status=MemoryItem.STATUS_ACTIVE,
        )

        if len(prefix) >= 4 and prefix[2] == "dataset":
            queryset = queryset.filter(
                scope_type=MemoryItem.SCOPE_DATASET,
                scope_key=str(prefix[3]),
            )
        else:
            queryset = queryset.filter(scope_type=MemoryItem.SCOPE_USER_GLOBAL)

        limit = op.limit or 10
        offset = op.offset or 0

        # 如果提供了查询文本，尝试进行语义搜索（向量 + 余弦相似度）
        query = getattr(op, "query", None)
        if query:
            try:
                query_vec = build_dense_embedding(query)
                memories = list(queryset)
                if any(m.embedding for m in memories):
                    scored = []
                    for m in memories:
                        sim = _cosine_similarity(query_vec, m.embedding) if m.embedding else 0.0
                        score = sim + (1.0 if m.pinned else 0.0)
                        scored.append((score, m))
                    scored.sort(key=lambda x: x[0], reverse=True)
                    return [_memory_to_item(m) for _, m in scored[offset : offset + limit]]
            except Exception:
                logger.warning("Memory semantic search failed, falling back to recency", exc_info=True)

        # 回退：置顶优先，然后按最近更新排序
        memories = list(queryset.order_by("-pinned", "-updated_at")[offset : offset + limit])
        return [_memory_to_item(m) for m in memories]

    def _handle_list_namespaces(self, op: ListNamespacesOp) -> list:
        """
        处理 list_namespaces 操作：列出所有存在的命名空间。

        从数据库中查询活跃记忆的 (user_id, scope_type, scope_key) 组合去重，
        并转换为 LangGraph 命名空间元组格式。

        参数：
          - op: ListNamespacesOp（未使用具体参数，全量返回）。

        返回：
          - list[tuple]: 命名空间元组列表，如 [("memories", "1"), ("memories", "1", "dataset", "5")]。
        """
        combos = (
            MemoryItem.objects.filter(status=MemoryItem.STATUS_ACTIVE)
            .values_list("user_id", "scope_type", "scope_key")
            .distinct()
        )
        result = []
        for user_id, scope_type, scope_key in combos:
            if scope_type == MemoryItem.SCOPE_DATASET:
                result.append(("memories", str(user_id), "dataset", scope_key))
            else:
                result.append(("memories", str(user_id)))
        return result


# 模块级别的 DjangoMemoryStore 单例实例。
# 类比 SpringBoot 中的 @Repository 单例 Bean。
django_memory_store = DjangoMemoryStore()
