from chat.models import ChatMessage, ChatSession
from llm.services.runtime_service import get_chat_provider

TITLE_MAX_LENGTH = 32


def _truncate_title(value, max_length):
    normalized = " ".join(str(value or "").split()).strip()
    if len(normalized) <= max_length:
        return normalized
    if max_length <= 3:
        return normalized[:max_length]
    return f"{normalized[: max_length - 3].rstrip()}..."


def _clean_generated_title(value):
    normalized = " ".join(str(value or "").split()).strip()
    normalized = normalized.strip("\"'“”‘’`#：:，,。. ")
    if not normalized:
        return ""
    return _truncate_title(normalized, TITLE_MAX_LENGTH)


def _build_title_messages(session):
    messages = list(
        session.messages.filter(status=ChatMessage.STATUS_COMPLETE)
        .order_by("sequence", "id")[:4]
    )
    transcript = "\n".join(
        f"{'用户' if message.role == ChatMessage.ROLE_USER else '助手'}：{message.content}"
        for message in messages
        if message.role in {ChatMessage.ROLE_USER, ChatMessage.ROLE_ASSISTANT}
    )
    return [
        {
            "role": "system",
            "content": (
                "你是 FinModPro 的会话标题生成器。"
                "请根据对话内容生成一个简洁中文标题，最多 12 个汉字，"
                "不要照抄用户原句，不要添加引号、标点或解释。"
            ),
        },
        {
            "role": "user",
            "content": f"对话内容：\n{transcript}\n\n只输出标题：",
        },
    ]


def _generate_ai_title(session):
    try:
        title = get_chat_provider().chat(
            messages=_build_title_messages(session),
            options={"temperature": 0.2, "max_tokens": 24},
        )
    except Exception:
        return ""
    return _clean_generated_title(title)


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

    if current_title and current_title != default_title and session.title_source != ChatSession.TITLE_SOURCE_AI:
        if session.title_status != ChatSession.TITLE_STATUS_READY:
            session.title_status = ChatSession.TITLE_STATUS_READY
            session.save(update_fields=["title_status", "updated_at"])
        return current_title

    if (
        session.title_source == ChatSession.TITLE_SOURCE_AI
        and session.title_status == ChatSession.TITLE_STATUS_READY
        and current_title
        and current_title != default_title
    ):
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

    complete_user_count = session.messages.filter(
        role=ChatMessage.ROLE_USER,
        status=ChatMessage.STATUS_COMPLETE,
    ).count()
    complete_assistant_count = session.messages.filter(
        role=ChatMessage.ROLE_ASSISTANT,
        status=ChatMessage.STATUS_COMPLETE,
    ).count()
    if complete_user_count != 1 or complete_assistant_count < 1:
        return current_title or default_title

    max_length = min(ChatSession._meta.get_field("title").max_length, TITLE_MAX_LENGTH)
    title = _generate_ai_title(session)
    if not title:
        title = _truncate_title(first_user_message.content, max_length) or default_title
    session.title = title
    session.title_status = ChatSession.TITLE_STATUS_READY
    session.title_source = ChatSession.TITLE_SOURCE_AI
    session.save(update_fields=["title", "title_status", "title_source", "updated_at"])
    return title
