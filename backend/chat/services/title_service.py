from chat.models import ChatMessage, ChatSession


def _truncate_title(value, max_length):
    normalized = " ".join(str(value or "").split()).strip()
    if len(normalized) <= max_length:
        return normalized
    if max_length <= 3:
        return normalized[:max_length]
    return f"{normalized[: max_length - 3].rstrip()}..."


def generate_session_title(*, session_id):
    session = ChatSession.objects.filter(id=session_id).first()
    if session is None:
        return None

    default_title = ChatSession._meta.get_field("title").default
    current_title = (session.title or "").strip()
    if session.title_source == ChatSession.TITLE_SOURCE_MANUAL:
        title = current_title or default_title
        if session.title_status != ChatSession.TITLE_STATUS_READY or session.title != title:
            session.title = title
            session.title_status = ChatSession.TITLE_STATUS_READY
            session.save(update_fields=["title", "title_status", "updated_at"])
        return title

    if current_title and current_title != default_title:
        if session.title_status != ChatSession.TITLE_STATUS_READY:
            session.title_status = ChatSession.TITLE_STATUS_READY
            session.save(update_fields=["title_status", "updated_at"])
        return current_title

    first_user_message = (
        session.messages.filter(
            role=ChatMessage.ROLE_USER,
            status=ChatMessage.STATUS_COMPLETE,
        )
        .order_by("sequence", "id")
        .first()
    )
    if first_user_message is None:
        return current_title or default_title

    max_length = ChatSession._meta.get_field("title").max_length
    title = _truncate_title(first_user_message.content, max_length) or default_title
    session.title = title
    session.title_status = ChatSession.TITLE_STATUS_READY
    session.title_source = ChatSession.TITLE_SOURCE_AI
    session.save(update_fields=["title", "title_status", "title_source", "updated_at"])
    return title
