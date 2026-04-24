import logging

from django.conf import settings
from django.db import transaction
from django.db.models import F, OuterRef, Q, Subquery, TextField, Value
from django.db.models.functions import Coalesce
from django.utils import timezone

from chat.models import ChatMessage, ChatSession

logger = logging.getLogger(__name__)


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
    default_title = ChatSession._meta.get_field("title").default
    normalized_input_title = (title or "").strip()
    normalized_title = normalized_input_title or default_title
    has_explicit_title_intent = bool(normalized_input_title)
    return ChatSession.objects.create(
        user=user,
        title=normalized_title,
        title_status=(
            ChatSession.TITLE_STATUS_READY
            if has_explicit_title_intent
            else ChatSession.TITLE_STATUS_PENDING
        ),
        title_source=(
            ChatSession.TITLE_SOURCE_MANUAL
            if has_explicit_title_intent
            else ChatSession.TITLE_SOURCE_AI
        ),
        context_filters=normalize_context_filters(context_filters),
    )


def get_chat_session_for_user(*, user, session_id):
    session = ChatSession.objects.prefetch_related("messages").filter(id=session_id).first()
    if session is None:
        raise ChatSession.DoesNotExist
    if session.user_id != user.id:
        raise PermissionError("无权限访问该会话。")
    return session


def delete_chat_session_for_user(*, user, session_id):
    session = get_chat_session_for_user(user=user, session_id=session_id)
    deleted_id = session.id
    session.delete()
    return deleted_id


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


def create_session_message(
    *,
    session,
    role,
    content,
    status=ChatMessage.STATUS_COMPLETE,
    citations=None,
    model_metadata=None,
    client_message_id="",
    **extra_fields,
):
    with transaction.atomic():
        message = ChatMessage.objects.create(
            session=session,
            role=role,
            content=content,
            status=status,
            citations_json=citations or [],
            model_metadata_json=model_metadata or {},
            client_message_id=client_message_id or "",
            **extra_fields,
        )
        timestamp = timezone.now()
        ChatSession.objects.filter(id=session.id).update(
            message_count=F("message_count") + 1,
            last_message_at=timestamp,
            updated_at=timestamp,
        )
        return message


def finalize_session_message(*, message, content, citations=None, model_metadata=None):
    with transaction.atomic():
        message.content = content
        message.status = ChatMessage.STATUS_COMPLETE
        message.citations_json = citations or []
        message.model_metadata_json = model_metadata or {}
        message.save(
            update_fields=[
                "content",
                "status",
                "citations_json",
                "model_metadata_json",
                "updated_at",
            ]
        )
        timestamp = timezone.now()
        ChatSession.objects.filter(id=message.session_id).update(
            last_message_at=timestamp,
            updated_at=timestamp,
        )
        return message


def fail_session_message(*, message, content="", citations=None, model_metadata=None):
    with transaction.atomic():
        message.content = content
        message.status = ChatMessage.STATUS_FAILED
        message.citations_json = citations or []
        message.model_metadata_json = model_metadata or {}
        message.save(
            update_fields=[
                "content",
                "status",
                "citations_json",
                "model_metadata_json",
                "updated_at",
            ]
        )
        timestamp = timezone.now()
        ChatSession.objects.filter(id=message.session_id).update(
            last_message_at=timestamp,
            updated_at=timestamp,
        )
        return message


def start_session_turn(*, session, question, client_message_id=""):
    with transaction.atomic():
        user_message = create_session_message(
            session=session,
            role=ChatMessage.ROLE_USER,
            content=question,
            client_message_id=client_message_id,
        )
        assistant_message = create_session_message(
            session=session,
            role=ChatMessage.ROLE_ASSISTANT,
            content="",
            status=ChatMessage.STATUS_PENDING,
        )
        return user_message, assistant_message


def persist_session_turn(*, session, question, answer, citations=None, model_metadata=None):
    with transaction.atomic():
        _, assistant_message = start_session_turn(session=session, question=question)
        return finalize_session_message(
            message=assistant_message,
            content=answer,
            citations=citations,
            model_metadata=model_metadata,
        )


def _dispatch_session_task(task, session_id):
    broker_url = str(getattr(settings, "CELERY_BROKER_URL", "") or "")
    should_run_inline = bool(getattr(settings, "CELERY_TASK_ALWAYS_EAGER", False)) or broker_url.startswith(
        "memory://"
    )
    if should_run_inline:
        return task.apply(args=(session_id,))
    return task.delay(session_id)


def dispatch_session_maintenance_tasks(*, session_id):
    from chat.tasks import (
        extract_session_memories_task,
        update_session_summary_task,
        update_session_title_task,
    )

    results = []
    for task in (
        update_session_title_task,
        update_session_summary_task,
        extract_session_memories_task,
    ):
        try:
            results.append(_dispatch_session_task(task, session_id))
        except Exception:
            logger.exception(
                "chat session maintenance enqueue failed",
                extra={"session_id": session_id, "task_name": task.name},
            )
    return results


def build_chat_session_export(*, session):
    messages = [
        {
            "id": message.id,
            "sequence": message.sequence,
            "role": message.role,
            "message_type": message.message_type,
            "status": message.status,
            "citations_json": message.citations_json,
            "model_metadata_json": message.model_metadata_json,
            "client_message_id": message.client_message_id,
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
            "title_status": session.title_status,
            "title_source": session.title_source,
            "rolling_summary": session.rolling_summary,
            "message_count": session.message_count,
            "last_message_at": (
                session.last_message_at.isoformat() if session.last_message_at else None
            ),
            "context_filters": normalize_context_filters(session.context_filters),
            "messages": messages,
            "created_at": session.created_at.isoformat() if session.created_at else None,
            "updated_at": session.updated_at.isoformat() if session.updated_at else None,
        },
        "exported_at": timezone.now().isoformat(),
    }
