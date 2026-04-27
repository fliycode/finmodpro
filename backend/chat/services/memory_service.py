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

_VALID_MEMORY_TYPES = {
    MemoryItem.TYPE_USER_PREFERENCE,
    MemoryItem.TYPE_WORK_RULE,
    MemoryItem.TYPE_CONFIRMED_FACT,
    MemoryItem.TYPE_PROJECT_BACKGROUND,
}
_MIN_CONFIDENCE = 0.7


def _get_memory_limit(limit):
    raw_value = limit
    if raw_value in (None, ""):
        raw_value = getattr(settings, "CHAT_MEMORY_RESULT_LIMIT", 5)
    try:
        return max(int(raw_value), 1)
    except (TypeError, ValueError):
        return 5


def _normalize_query(value):
    return " ".join(str(value or "").split()).strip()


def list_memory_items_for_user(*, user, scope_type="", scope_key="", query=""):
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
    return MemoryItem.objects.get(id=memory_id, user=user)


def list_memory_evidence_for_memory(*, memory_item):
    return list(memory_item.evidence_items.order_by("-created_at", "-id"))


def record_memory_view(*, memory_item, actor_user):
    return MemoryActionLog.objects.create(
        memory_item=memory_item,
        actor_user=actor_user,
        action=MemoryActionLog.ACTION_VIEW,
        details_json={},
    )


def set_memory_pin_state(*, memory_item, actor_user, pinned):
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
    return " ".join(str(value or "").split()).strip()


def _get_dataset_scope_key(session):
    context_filters = getattr(session, "context_filters", None)
    if not isinstance(context_filters, dict):
        return ""
    dataset_id = context_filters.get("dataset_id")
    if dataset_id in (None, ""):
        return ""
    return str(dataset_id)


def _build_memory_fingerprint(*, user_id, scope_type, scope_key, memory_type, content):
    fingerprint_source = f"{user_id}|{scope_type}|{scope_key}|{memory_type}|{content}"
    return hashlib.sha256(fingerprint_source.encode("utf-8")).hexdigest()


def extract_memories_with_llm(*, session_id: int) -> int:
    """Extract memories from a session using LLM and persist them via DjangoMemoryStore.

    Returns the number of newly created MemoryItem records.
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
        )
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
