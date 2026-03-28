from django.db.models import OuterRef, Subquery, TextField, Value
from django.db.models.functions import Coalesce

from chat.models import ChatMessage, ChatSession


def create_chat_session(*, user, title="", context_filters=None):
    normalized_title = (title or "").strip() or ChatSession._meta.get_field("title").default
    return ChatSession.objects.create(
        user=user,
        title=normalized_title,
        context_filters=context_filters or {},
    )


def get_chat_session_for_user(*, user, session_id):
    session = ChatSession.objects.prefetch_related("messages").filter(id=session_id).first()
    if session is None:
        raise ChatSession.DoesNotExist
    if session.user_id != user.id:
        raise PermissionError("无权限访问该会话。")
    return session


def list_chat_sessions_for_user(*, user):
    last_message_content = ChatMessage.objects.filter(session_id=OuterRef("pk")).order_by(
        "-sequence", "-id"
    )
    return (
        ChatSession.objects.filter(user=user)
        .annotate(
            last_message_preview=Coalesce(
                Subquery(last_message_content.values("content")[:1]),
                Value("", output_field=TextField()),
            )
        )
        .order_by("-updated_at", "-id")
    )
