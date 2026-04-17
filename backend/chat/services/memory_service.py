import hashlib

from django.conf import settings
from django.db.models import Q

from chat.models import ChatMessage, ChatSession, MemoryEvidence, MemoryItem


def _get_memory_limit(limit):
    raw_value = limit
    if raw_value in (None, ""):
        raw_value = getattr(settings, "CHAT_MEMORY_RESULT_LIMIT", 5)
    try:
        return max(int(raw_value), 1)
    except (TypeError, ValueError):
        return 5


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

    normalized_query = " ".join(str(query or "").split()).strip()
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


def _classify_memory_content(content):
    normalized_content = _normalize_text(content)
    if not normalized_content:
        return None

    work_rule_cues = ("请记住", "记住：", "务必", "必须", "规则是", "请按")
    if any(cue in normalized_content for cue in work_rule_cues):
        return MemoryItem.TYPE_WORK_RULE, normalized_content

    preference_cues = ("以后请", "请先", "我希望", "我喜欢", "默认", "偏好")
    if any(cue in normalized_content for cue in preference_cues):
        return MemoryItem.TYPE_USER_PREFERENCE, normalized_content

    return None


def _build_memory_scope(*, session, memory_type):
    if memory_type == MemoryItem.TYPE_WORK_RULE:
        dataset_scope_key = _get_dataset_scope_key(session)
        if dataset_scope_key:
            return MemoryItem.SCOPE_DATASET, dataset_scope_key
    return MemoryItem.SCOPE_USER_GLOBAL, ""


def _build_memory_title(*, memory_type, content):
    prefix = "用户偏好" if memory_type == MemoryItem.TYPE_USER_PREFERENCE else "工作规则"
    snippet = content[:32]
    return f"{prefix}：{snippet}"


def _build_memory_fingerprint(*, user_id, scope_type, scope_key, memory_type, content):
    fingerprint_source = f"{user_id}|{scope_type}|{scope_key}|{memory_type}|{content}"
    return hashlib.sha256(fingerprint_source.encode("utf-8")).hexdigest()


def extract_session_memories(*, session_id):
    session = ChatSession.objects.select_related("user").filter(id=session_id).first()
    if session is None:
        return []

    extracted_items = []
    messages = session.messages.filter(
        role=ChatMessage.ROLE_USER,
        status=ChatMessage.STATUS_COMPLETE,
    ).order_by("sequence", "id")

    for message in messages:
        classification = _classify_memory_content(message.content)
        if classification is None:
            continue

        memory_type, normalized_content = classification
        scope_type, scope_key = _build_memory_scope(session=session, memory_type=memory_type)
        fingerprint = _build_memory_fingerprint(
            user_id=session.user_id,
            scope_type=scope_type,
            scope_key=scope_key,
            memory_type=memory_type,
            content=normalized_content,
        )
        memory_item = MemoryItem.objects.filter(
            user=session.user,
            fingerprint=fingerprint,
        ).first()

        created_item = False
        if memory_item is None:
            memory_item = MemoryItem.objects.create(
                user=session.user,
                scope_type=scope_type,
                scope_key=scope_key,
                memory_type=memory_type,
                title=_build_memory_title(memory_type=memory_type, content=normalized_content),
                content=normalized_content,
                fingerprint=fingerprint,
                source_kind=MemoryItem.SOURCE_AUTO,
                status=MemoryItem.STATUS_ACTIVE,
            )
            created_item = True
        elif memory_item.status != MemoryItem.STATUS_ACTIVE:
            continue

        _, created_evidence = MemoryEvidence.objects.get_or_create(
            memory_item=memory_item,
            message=message,
            defaults={
                "session": session,
                "evidence_excerpt": normalized_content,
                "extractor_version": "task3a_memory_v1",
            },
        )
        if created_item or created_evidence:
            extracted_items.append(memory_item)

    return extracted_items
