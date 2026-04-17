from django.conf import settings
from django.db.models import Q

from chat.models import ChatSession, MemoryItem


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


def extract_session_memories(*, session_id):
    session = ChatSession.objects.select_related("user").filter(id=session_id).first()
    if session is None:
        return []

    return []
