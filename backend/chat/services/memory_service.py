"""
Chat 记忆管理服务层（Memory Service）。

类比 SpringBoot：
  - 相当于 @Service 类，负责记忆条目的 CRUD 操作、搜索和 LLM 驱动的自动记忆提取。
  - Django ORM 的 objects.filter / objects.get / objects.create 相当于 Spring Data JPA Repository 的方法。

模块功能：
  1. 记忆的增删改查和置顶操作
  2. 记忆的文本搜索（基于数据库 LIKE 查询）
  3. 记忆的证据管理
  4. 操作审计日志记录
  5. LLM 驱动的自动记忆提取（从会话中提取知识偏好和事实）
  6. 基于 SHA256 指纹的记忆去重
"""

import hashlib
import json
import logging

from django.conf import settings
from django.db import transaction
from django.db.models import Q

from chat.models import ChatMessage, ChatSession, MemoryActionLog, MemoryEvidence, MemoryItem
from llm.services.prompt_service import render_prompt
from llm.services.runtime_service import get_chat_provider

logger = logging.getLogger(__name__)

# 允许 LLM 提取的记忆类型白名单
_VALID_MEMORY_TYPES = {
    MemoryItem.TYPE_USER_PREFERENCE,
    MemoryItem.TYPE_WORK_RULE,
    MemoryItem.TYPE_CONFIRMED_FACT,
    MemoryItem.TYPE_PROJECT_BACKGROUND,
}
# 记忆提取的最低置信度阈值（低于此值的候选记忆将被丢弃）
_MIN_CONFIDENCE = 0.7


def _get_memory_limit(limit):
    """
    获取记忆搜索/加载的数量上限。

    参数：
      - limit: int|None|str 传入的条数限制。

    返回：
      - int: 正整数限制值，至少为 1。无效值时回退到 settings.CHAT_MEMORY_RESULT_LIMIT（默认 5）。
    """
    raw_value = limit
    if raw_value in (None, ""):
        raw_value = getattr(settings, "CHAT_MEMORY_RESULT_LIMIT", 5)
    try:
        return max(int(raw_value), 1)
    except (TypeError, ValueError):
        return 5


def _normalize_query(value):
    """
    标准化查询字符串：去除多余空白，将连续空白替换为单个空格。

    参数：
      - value: str 原始查询文本。

    返回：
      - str: 标准化后的查询文本。
    """
    return " ".join(str(value or "").split()).strip()


def list_memory_items_for_user(*, user, scope_type="", scope_key="", query=""):
    """
    查询当前用户活跃记忆列表，支持作用域和关键词过滤。

    参数（均为关键字参数）：
      - user: User 模型实例（必填）。
      - scope_type: str 作用域类型（可选），如 "user_global" / "dataset"。
      - scope_key: str 作用域键值（可选），如 dataset_id。
      - query: str 关键词搜索（可选），在 title 和 content 中做 LIKE 匹配。

    返回：
      - list[MemoryItem]: 符合条件的活跃记忆列表，置顶优先、最近更新次之。
    """
    queryset = MemoryItem.objects.filter(
        user=user,
        status=MemoryItem.STATUS_ACTIVE,
    )

    normalized_scope_type = str(scope_type or "").strip()
    if normalized_scope_type:
        queryset = queryset.filter(scope_type=normalized_scope_type)

    normalized_scope_key = str(scope_key or "").strip()
    if normalized_scope_key:
        queryset = queryset.filter(scope_key=normalized_scope_key)

    normalized_query = _normalize_query(query)
    if normalized_query:
        for token in normalized_query.split():
            queryset = queryset.filter(
                Q(title__icontains=token) | Q(content__icontains=token)
            )

    return list(queryset.order_by("-pinned", "-updated_at", "-id"))


def get_memory_item_for_user(*, user, memory_id):
    """
    按 ID 获取用户的单条记忆条目（含权限校验）。

    参数（均为关键字参数）：
      - user: User 模型实例。
      - memory_id: int 记忆条目 ID。

    返回：
      - MemoryItem: 对应用户的记忆条目。

    异常：
      - MemoryItem.DoesNotExist: 记忆不存在或不属于该用户。
    """
    return MemoryItem.objects.get(id=memory_id, user=user)


def list_memory_evidence_for_memory(*, memory_item):
    """
    列出指定记忆的所有关联证据记录。

    参数（均为关键字参数）：
      - memory_item: MemoryItem 实例。

    返回：
      - list[MemoryEvidence]: 按创建时间倒序的证据列表。
    """
    return list(memory_item.evidence_items.order_by("-created_at", "-id"))


def record_memory_view(*, memory_item, actor_user):
    """
    记录一次"查看记忆"的操作审计日志。

    参数（均为关键字参数）：
      - memory_item: MemoryItem 实例，被查看的记忆。
      - actor_user: User 模型实例，执行查看操作的用户。

    返回：
      - MemoryActionLog: 新创建的操作日志条目。
    """
    return MemoryActionLog.objects.create(
        memory_item=memory_item,
        actor_user=actor_user,
        action=MemoryActionLog.ACTION_VIEW,
        details_json={},
    )


def set_memory_pin_state(*, memory_item, actor_user, pinned):
    """
    切换记忆的置顶状态，并记录审计日志。

    在一个数据库事务中完成：更新 pinned 字段 + 写入操作日志。

    参数（均为关键字参数）：
      - memory_item: MemoryItem 实例。
      - actor_user: User 模型实例，执行操作的用户。
      - pinned: bool True=置顶，False=取消置顶。

    返回：
      - MemoryItem: 更新后的记忆条目（pinned 字段已变更）。
    """
    with transaction.atomic():
        memory_item.pinned = pinned
        memory_item.save(update_fields=["pinned", "updated_at"])
        MemoryActionLog.objects.create(
            memory_item=memory_item,
            actor_user=actor_user,
            action=MemoryActionLog.ACTION_PIN if pinned else MemoryActionLog.ACTION_UNPIN,
            details_json={"pinned": pinned},
        )
    return memory_item


def delete_memory_item(*, memory_item, actor_user):
    """
    软删除记忆条目，并记录审计日志。

    不真正删除数据库记录，仅将 status 设为 "deleted"。

    参数（均为关键字参数）：
      - memory_item: MemoryItem 实例。
      - actor_user: User 模型实例，执行删除操作的用户。

    返回：
      - MemoryItem: 更新后的记忆条目（status 已变为 deleted）。
    """
    with transaction.atomic():
        memory_item.status = MemoryItem.STATUS_DELETED
        memory_item.save(update_fields=["status", "updated_at"])
        MemoryActionLog.objects.create(
            memory_item=memory_item,
            actor_user=actor_user,
            action=MemoryActionLog.ACTION_DELETE,
            details_json={},
        )
    return memory_item


def search_memories(*, user, query="", dataset_id=None, limit=None):
    """
    搜索用户的活跃记忆（用于 RAG 上下文加载）。

    搜索范围：用户全局记忆 + 指定数据集的关联记忆。
    支持关键词在 title/content 中做 LIKE 匹配。

    参数（均为关键字参数）：
      - user: User 模型实例。
      - query: str 搜索关键词。
      - dataset_id: str|int|None 数据集 ID（可选）。
      - limit: int|None 返回条数上限。

    返回：
      - list[MemoryItem]: 匹配的记忆列表。
    """
    queryset = MemoryItem.objects.filter(
        user=user,
        status=MemoryItem.STATUS_ACTIVE,
    )

    scope_filter = Q(scope_type=MemoryItem.SCOPE_USER_GLOBAL)
    if dataset_id not in (None, ""):
        scope_filter |= Q(
            scope_type=MemoryItem.SCOPE_DATASET,
            scope_key=str(dataset_id),
        )
    queryset = queryset.filter(scope_filter)

    normalized_query = _normalize_query(query)
    if normalized_query:
        for token in normalized_query.split():
            queryset = queryset.filter(
                Q(title__icontains=token) | Q(content__icontains=token)
            )

    return list(queryset[: _get_memory_limit(limit)])


def _normalize_text(value):
    """
    将文本标准化为单行字符串。

    参数：
      - value: str 原始文本。

    返回：
      - str: 标准化后的单行文本。
    """
    return " ".join(str(value or "").split()).strip()


def _get_dataset_scope_key(session):
    """
    从会话的 context_filters 中提取 dataset_id 作为作用域键值。

    参数：
      - session: ChatSession 实例。

    返回：
      - str: dataset_id 字符串，如果没有或无效则返回空字符串。
    """
    context_filters = getattr(session, "context_filters", None)
    if not isinstance(context_filters, dict):
        return ""
    dataset_id = context_filters.get("dataset_id")
    if dataset_id in (None, ""):
        return ""
    return str(dataset_id)


def _build_memory_fingerprint(*, user_id, scope_type, scope_key, memory_type, content):
    """
    为记忆条目生成 SHA256 指纹，用于去重。

    将 user_id + scope_type + scope_key + memory_type + content 拼接后计算哈希，
    相同内容的记忆将产生相同指纹，避免重复入库。

    参数（均为关键字参数）：
      - user_id: int 用户 ID。
      - scope_type: str 作用域类型。
      - scope_key: str 作用域键值。
      - memory_type: str 记忆类型。
      - content: str 记忆内容。

    返回：
      - str: 64 位十六进制 SHA256 指纹字符串。
    """
    fingerprint_source = f"{user_id}|{scope_type}|{scope_key}|{memory_type}|{content}"
    return hashlib.sha256(fingerprint_source.encode("utf-8")).hexdigest()


def extract_memories_with_llm(*, session_id: int) -> int:
    """
    使用 LLM 从会话中自动提取长期记忆，并通过 DjangoMemoryStore 持久化。

    流程：
      1. 获取会话及所有已完成的消息
      2. 将对话内容拼接为文本
      3. 调用 LLM 提取记忆条目（JSON 格式输出）
      4. 解析 LLM 返回的 JSON
      5. 校验记忆类型、置信度等约束
      6. 通过指纹去重后写入 MemoryItem 和 MemoryEvidence

    类比 SpringBoot：
      - 相当于 @Service 方法中调用 LLM 进行知识抽取的后台任务。

    参数（均为关键字参数）：
      - session_id: int 会话 ID。

    返回：
      - int: 新创建的记忆条目数（0 表示无新记忆或提取失败）。
    """
    session = ChatSession.objects.select_related("user").filter(id=session_id).first()
    if session is None:
        return 0

    messages = list(
        session.messages.filter(status=ChatMessage.STATUS_COMPLETE)
        .exclude(role=ChatMessage.ROLE_SYSTEM)
        .order_by("sequence", "id")
    )
    if not messages:
        return 0

    role_labels = {
        ChatMessage.ROLE_USER: "用户",
        ChatMessage.ROLE_ASSISTANT: "助手",
    }
    conversation_lines = [
        f"{role_labels.get(m.role, m.role)}: {m.content.strip()}"
        for m in messages
        if m.content.strip()
    ]
    conversation_text = "\n".join(conversation_lines)
    if not conversation_text:
        return 0

    prompt = render_prompt("chat/extract_memories.txt", conversation=conversation_text)
    try:
        provider = get_chat_provider()
        response = provider.chat(
            messages=[{"role": "user", "content": prompt}],
            options={"temperature": 0, "max_tokens": 512},
        ).content
    except Exception:
        logger.exception("LLM memory extraction failed for session %s", session_id)
        return 0

    raw_text = response.strip() if isinstance(response, str) else ""
    try:
        extracted = json.loads(raw_text)
        if not isinstance(extracted, list):
            extracted = []
    except (json.JSONDecodeError, ValueError):
        logger.warning("Could not parse LLM memory extraction JSON for session %s: %r", session_id, raw_text)
        return 0

    from chat.services.store import django_memory_store

    created_count = 0
    for item in extracted:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title", "")).strip()[:255]
        content = str(item.get("content", "")).strip()
        memory_type = str(item.get("memory_type", "")).strip()
        confidence_raw = item.get("confidence_score", 0.0)
        if not content or memory_type not in _VALID_MEMORY_TYPES:
            continue
        try:
            confidence = float(confidence_raw)
        except (TypeError, ValueError):
            confidence = 0.0
        confidence = max(0.0, min(1.0, confidence))
        if confidence < _MIN_CONFIDENCE:
            continue

        fingerprint = _build_memory_fingerprint(
            user_id=session.user_id,
            scope_type=MemoryItem.SCOPE_USER_GLOBAL,
            scope_key="",
            memory_type=memory_type,
            content=content,
        )

        with transaction.atomic():
            existing = MemoryItem.objects.filter(
                user=session.user, fingerprint=fingerprint
            ).first()

            if existing is not None:
                if existing.status != MemoryItem.STATUS_ACTIVE:
                    continue
                memory_item = existing
                new_item = False
            else:
                ns = ("memories", str(session.user_id))
                django_memory_store.put(ns, fingerprint, {
                    "title": title,
                    "content": content,
                    "memory_type": memory_type,
                    "confidence_score": confidence,
                    "pinned": False,
                    "source_kind": MemoryItem.SOURCE_AUTO,
                })
                memory_item = MemoryItem.objects.get(user=session.user, fingerprint=fingerprint)
                new_item = True

            _, evidence_created = MemoryEvidence.objects.get_or_create(
                memory_item=memory_item,
                session=session,
                defaults={
                    "evidence_excerpt": content[:500],
                    "extractor_version": "llm_v1",
                },
            )
            if new_item or evidence_created:
                created_count += 1

    return created_count


def _normalize_text(value):
    return " ".join(str(value or "").split()).strip()


def _get_dataset_scope_key(session):
    context_filters = getattr(session, "context_filters", None)
    if not isinstance(context_filters, dict):
        return ""
    dataset_id = context_filters.get("dataset_id")
    if dataset_id in (None, ""):
        return ""
    return str(dataset_id)
