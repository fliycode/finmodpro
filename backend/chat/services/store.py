import asyncio
import logging
import math
from typing import Iterable

from langgraph.store.base import BaseStore, GetOp, Item, ListNamespacesOp, Op, PutOp, SearchOp

from chat.models import MemoryItem
from knowledgebase.services.embedding_service import build_dense_embedding

logger = logging.getLogger(__name__)


def _cosine_similarity(vec_a: list, vec_b: list) -> float:
    """Pure-Python cosine similarity for two float vectors."""
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _namespace_to_user_id(namespace: tuple) -> int:
    return int(namespace[1])


def _namespace_to_scope(namespace: tuple) -> tuple:
    """Map LangGraph namespace tuple → (scope_type, scope_key)."""
    if len(namespace) >= 4 and namespace[2] == "dataset":
        return MemoryItem.SCOPE_DATASET, str(namespace[3])
    return MemoryItem.SCOPE_USER_GLOBAL, ""


def _scope_to_namespace(memory: MemoryItem) -> tuple:
    base = ("memories", str(memory.user_id))
    if memory.scope_type == MemoryItem.SCOPE_DATASET:
        return base + ("dataset", memory.scope_key)
    return base


def _memory_to_item(memory: MemoryItem) -> Item:
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
    """LangGraph BaseStore backed by the MemoryItem Django model."""

    def batch(self, ops: Iterable[Op]) -> list:
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
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self.batch, list(ops))

    def _handle_put(self, op: PutOp):
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

        # Try semantic ranking when a query is provided.
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

        # Fallback: pinned items first, then by recency.
        memories = list(queryset.order_by("-pinned", "-updated_at")[offset : offset + limit])
        return [_memory_to_item(m) for m in memories]

    def _handle_list_namespaces(self, op: ListNamespacesOp) -> list:
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


django_memory_store = DjangoMemoryStore()
