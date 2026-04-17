from django.conf import settings
from django.db import transaction

from chat.models import ChatMessage, ChatSession


def _get_summary_trigger():
    raw_value = getattr(settings, "CHAT_SUMMARY_TRIGGER_MESSAGES", 6)
    try:
        return max(int(raw_value), 1)
    except (TypeError, ValueError):
        return 6


def _collapse_text(value):
    return " ".join(str(value or "").split()).strip()


def update_session_summary(*, session_id):
    with transaction.atomic():
        session = ChatSession.objects.select_for_update().filter(id=session_id).first()
        if session is None:
            return None

        messages = list(
            session.messages.filter(status=ChatMessage.STATUS_COMPLETE).order_by("sequence", "id")
        )
        if not messages:
            return session.rolling_summary

        last_message_id = messages[-1].id
        if (
            session.summary_updated_through_message_id is not None
            and session.summary_updated_through_message_id >= last_message_id
        ):
            return session.rolling_summary

        if len(messages) < _get_summary_trigger():
            return session.rolling_summary

        role_labels = {
            ChatMessage.ROLE_USER: "用户",
            ChatMessage.ROLE_ASSISTANT: "助手",
            ChatMessage.ROLE_SYSTEM: "系统",
        }
        summary_window = messages[-_get_summary_trigger() :]
        summary = " | ".join(
            f"{role_labels.get(message.role, message.role)}: {_collapse_text(message.content)}"
            for message in summary_window
            if _collapse_text(message.content)
        )
        session.rolling_summary = summary
        session.summary_updated_through_message_id = last_message_id
        session.save(
            update_fields=[
                "rolling_summary",
                "summary_updated_through_message_id",
                "updated_at",
            ]
        )
        return summary
