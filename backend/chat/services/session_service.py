from chat.models import ChatSession


def create_chat_session(*, user, title="", context_filters=None):
    normalized_title = (title or "").strip() or ChatSession._meta.get_field("title").default
    return ChatSession.objects.create(
        user=user,
        title=normalized_title,
        context_filters=context_filters or {},
    )
