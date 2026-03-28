from chat.models import ChatSession


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
