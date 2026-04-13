from django.db.models import OuterRef, Q, Subquery, TextField, Value
from django.db.models.functions import Coalesce
from django.utils import timezone

from chat.models import ChatMessage, ChatSession


INTEGER_FILTER_KEYS = {"dataset_id", "document_id"}


def _coerce_filter_value(key, value):
    if value in (None, ""):
        return None
    if key not in INTEGER_FILTER_KEYS:
        return value
    try:
        return int(value)
    except (TypeError, ValueError):
        return value


def normalize_context_filters(context_filters=None):
    if not isinstance(context_filters, dict):
        return {}

    normalized = {}
    for key, value in context_filters.items():
        normalized_value = _coerce_filter_value(key, value)
        if normalized_value in (None, ""):
            continue
        normalized[key] = normalized_value
    return normalized


def create_chat_session(*, user, title="", context_filters=None):
    normalized_title = (title or "").strip() or ChatSession._meta.get_field("title").default
    return ChatSession.objects.create(
        user=user,
        title=normalized_title,
        context_filters=normalize_context_filters(context_filters),
    )


def get_chat_session_for_user(*, user, session_id):
    session = ChatSession.objects.prefetch_related("messages").filter(id=session_id).first()
    if session is None:
        raise ChatSession.DoesNotExist
    if session.user_id != user.id:
        raise PermissionError("无权限访问该会话。")
    return session


def list_chat_sessions_for_user(*, user, dataset_id=None, keyword=""):
    last_message_content = ChatMessage.objects.filter(session_id=OuterRef("pk")).order_by(
        "-sequence", "-id"
    )
    queryset = (
        ChatSession.objects.filter(user=user)
        .annotate(
            last_message_preview=Coalesce(
                Subquery(last_message_content.values("content")[:1]),
                Value("", output_field=TextField()),
            )
        )
    )

    normalized_dataset_id = _coerce_filter_value("dataset_id", dataset_id)
    if normalized_dataset_id is not None:
        queryset = queryset.filter(
            Q(context_filters__dataset_id=normalized_dataset_id)
            | Q(context_filters__dataset_id=str(normalized_dataset_id))
        )

    normalized_keyword = (keyword or "").strip()
    if normalized_keyword:
        queryset = queryset.filter(
            Q(title__icontains=normalized_keyword)
            | Q(messages__content__icontains=normalized_keyword)
        ).distinct()

    return queryset.order_by("-updated_at", "-id")


def persist_session_turn(*, session, question, answer):
    ChatMessage.objects.create(
        session=session,
        role=ChatMessage.ROLE_USER,
        content=question,
    )
    ChatMessage.objects.create(
        session=session,
        role=ChatMessage.ROLE_ASSISTANT,
        content=answer,
    )
    ChatSession.objects.filter(id=session.id).update(updated_at=timezone.now())


def build_chat_session_export(*, session):
    messages = [
        {
            "id": message.id,
            "sequence": message.sequence,
            "role": message.role,
            "message_type": message.message_type,
            "content": message.content,
            "created_at": message.created_at.isoformat() if message.created_at else None,
            "updated_at": message.updated_at.isoformat() if message.updated_at else None,
        }
        for message in session.messages.all()
    ]
    return {
        "session": {
            "id": session.id,
            "title": session.title,
            "context_filters": normalize_context_filters(session.context_filters),
            "messages": messages,
            "created_at": session.created_at.isoformat() if session.created_at else None,
            "updated_at": session.updated_at.isoformat() if session.updated_at else None,
        },
        "exported_at": timezone.now().isoformat(),
    }
