"""
Chat 会话管理服务层（Session Service）。

类比 SpringBoot：
  - 相当于 @Service 类，负责会话（ChatSession）和消息（ChatMessage）的 CRUD 操作。
  - Django ORM 的 create/update/filter 相当于 Spring Data JPA Repository 的操作。
  - transaction.atomic() 上下文管理器相当于 @Transactional 注解。

模块功能：
  1. 会话的创建、查询、删除、列表
  2. 会话内消息的创建、完成、失败状态管理
  3. 一轮对话的开始（同时创建用户消息和 assistant 占位消息）
  4. 上下文过滤器的标准化处理
  5. 会话导出（用于备份/下载）
  6. Celery 异步维护任务的派发（标题生成、摘要更新、记忆提取）
"""

import logging

from django.conf import settings
from django.db import transaction
from django.db.models import F, OuterRef, Q, Subquery, TextField, Value
from django.db.models.functions import Coalesce
from django.utils import timezone

from chat.models import ChatMessage, ChatSession

logger = logging.getLogger(__name__)

# 需要转换为整数的上下文过滤键名集合
INTEGER_FILTER_KEYS = {"dataset_id", "document_id"}


def _coerce_filter_value(key, value):
    """
    将上下文过滤器的值转换为正确的类型。

    对于 INTEGER_FILTER_KEYS 中的键，尝试转为整数；其他键保持原样。
    None 和空字符串统一返回 None。

    参数：
      - key: str 过滤键名。
      - value: Any 过滤值。

    返回：
      - int|str|None: 转换后的过滤值。
    """
    if value in (None, ""):
        return None
    if key not in INTEGER_FILTER_KEYS:
        return value
    try:
        return int(value)
    except (TypeError, ValueError):
        return value


def normalize_context_filters(context_filters=None):
    """
    标准化上下文过滤条件字典。

    过滤掉值为 None 或空字符串的项，将数值型键转换为整数。

    参数：
      - context_filters: dict|None 原始过滤条件。

    返回：
      - dict: 标准化后的过滤条件字典（无空值）。
    """
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
    """
    创建一条新的聊天会话。

    类比 SpringBoot：
      - 相当于 @Transactional 的 @Service 方法，创建 Entity 记录。

    参数（均为关键字参数）：
      - user: User 模型实例（必填）。
      - title: str 会话标题，默认从模型字段 default 取值（"新会话"）。
      - context_filters: dict|None 上下文过滤器。

    返回：
      - ChatSession: 新创建的会话对象。

    标题状态逻辑：
      - 如果用户提供了明确的标题，标记为 TITLE_STATUS_READY + TITLE_SOURCE_MANUAL。
      - 否则标记为 TITLE_STATUS_PENDING + TITLE_SOURCE_AI（等待 AI 自动生成）。
    """
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
    """
    获取指定用户的会话（含权限校验）。

    参数（均为关键字参数）：
      - user: User 模型实例。
      - session_id: int 会话 ID。

    返回：
      - ChatSession: 预制了 messages 关联查询的会话对象。

    异常：
      - ChatSession.DoesNotExist: 会话不存在。
      - PermissionError: 会话不属于当前用户。
    """
    session = ChatSession.objects.prefetch_related("messages").filter(id=session_id).first()
    if session is None:
        raise ChatSession.DoesNotExist
    if session.user_id != user.id:
        raise PermissionError("无权限访问该会话。")
    return session


def delete_chat_session_for_user(*, user, session_id):
    """
    删除指定用户的会话（级联删除所有关联消息）。

    参数（均为关键字参数）：
      - user: User 模型实例。
      - session_id: int 会话 ID。

    返回：
      - int: 被删除的会话 ID。

    异常：
      - ChatSession.DoesNotExist: 会话不存在。
      - PermissionError: 会话不属于当前用户。
    """
    session = get_chat_session_for_user(user=user, session_id=session_id)
    deleted_id = session.id
    session.delete()
    return deleted_id


def list_chat_sessions_for_user(*, user, dataset_id=None, keyword=""):
    """
    列出当前用户的会话列表（支持过滤和搜索）。

    使用子查询获取每个会话的最后一条消息作为预览。

    参数（均为关键字参数）：
      - user: User 模型实例。
      - dataset_id: int|str|None 数据集 ID（可选过滤）。
      - keyword: str 关键词搜索（匹配标题或消息内容）。

    返回：
      - QuerySet[ChatSession]: 按 updated_at 倒序排列的会话查询集。
        每个会话附加了 last_message_preview 注释字段。
    """
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
    """
    在会话中创建一条新消息，并更新会话的计数器和时间戳。

    在一个数据库事务中完成：创建消息 + 更新会话的 message_count / last_message_at。

    类比 SpringBoot：
      - 相当于 @Transactional 方法，涉及多表原子操作。

    参数（均为关键字参数）：
      - session: ChatSession 实例（必填）。
      - role: str 消息角色（user/assistant/system）。
      - content: str 消息内容。
      - status: str 消息状态，默认 STATUS_COMPLETE。
      - citations: list|None 引用列表。
      - model_metadata: dict|None 模型元数据。
      - client_message_id: str 客户端消息 ID。
      - **extra_fields: 额外的 ChatMessage 字段。

    返回：
      - ChatMessage: 新创建的消息对象。
    """
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
    """
    将一条 pending 状态的 assistant 消息标记为 complete。

    在一个数据库事务中更新消息内容和状态，同时更新会话的时间戳。

    参数（均为关键字参数）：
      - message: ChatMessage 实例（assistant 角色，通常 status=pending）。
      - content: str LLM 生成的完整回答文本。
      - citations: list|None 过滤后的引用列表。
      - model_metadata: dict|None 模型元数据（如 answer_mode）。

    返回：
      - ChatMessage: 更新后的消息对象。
    """
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
    """
    将一条 pending 状态的 assistant 消息标记为 failed。

    在 LLM 调用失败时调用，保留已生成的部分内容并标记为失败状态。

    参数（均为关键字参数）：
      - message: ChatMessage 实例（assistant 角色）。
      - content: str 失败前已生成的部分文本。
      - citations: list|None 引用列表。
      - model_metadata: dict|None 模型元数据。

    返回：
      - ChatMessage: 更新后的消息对象。
    """
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
    """
    开始一轮对话：同时创建用户消息和 assistant 占位消息。

    这是对话回合的原子入口。在同一个事务中创建两条消息：
      - 用户消息（status=complete，content=用户提问）
      - AI 消息（status=pending，content=""，后续由 LLM 回填）

    类比 SpringBoot：
      - 相当于 @Transactional 方法，一次创建两条关联记录。

    参数（均为关键字参数）：
      - session: ChatSession 实例（必填）。
      - question: str 用户提问文本。
      - client_message_id: str 客户端消息 ID（可选）。

    返回：
      - tuple[ChatMessage, ChatMessage]: (user_message, assistant_message)。
    """
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
    """
    在一步内完成一轮对话：创建用户消息和 assistant 消息并标记完成。

    这是 start_session_turn + finalize_session_message 的组合快捷方法。

    参数（均为关键字参数）：
      - session: ChatSession 实例（必填）。
      - question: str 用户提问文本。
      - answer: str LLM 生成的完整回答。
      - citations: list|None 引用列表。
      - model_metadata: dict|None 模型元数据。

    返回：
      - ChatMessage: 完成状态的 assistant 消息。
    """
    with transaction.atomic():
        _, assistant_message = start_session_turn(session=session, question=question)
        return finalize_session_message(
            message=assistant_message,
            content=answer,
            citations=citations,
            model_metadata=model_metadata,
        )


def _dispatch_session_task(task, session_id):
    """
    将 Celery 异步任务加入队列执行。

    如果配置了 CELERY_TASK_ALWAYS_EAGER=True 或 CELERY_BROKER_URL 以 "memory://" 开头
    （如测试环境），则在当前进程同步执行；否则通过 Celery 异步执行。

    类比 SpringBoot：
      - 相当于 @Async 方法执行或通过消息队列（RabbitMQ/Kafka）异步派发。

    参数：
      - task: Celery Task 实例。
      - session_id: int 会话 ID。

    返回：
      - AsyncResult|EagerResult: Celery 任务结果对象。
    """
    broker_url = str(getattr(settings, "CELERY_BROKER_URL", "") or "")
    should_run_inline = bool(getattr(settings, "CELERY_TASK_ALWAYS_EAGER", False)) or broker_url.startswith(
        "memory://"
    )
    if should_run_inline:
        return task.apply(args=(session_id,))
    return task.delay(session_id)


def dispatch_session_maintenance_tasks(*, session_id):
    """
    派发会话维护相关的三个 Celery 异步任务。

    任务列表（按顺序）：
      1. update_session_title_task - 更新会话标题（AI 生成）
      2. update_session_summary_task - 更新滚动摘要
      3. extract_session_memories_task - 提取长期记忆

    参数（均为关键字参数）：
      - session_id: int 会话 ID。

    返回：
      - list: Celery 任务结果对象列表。如果某个任务入队失败，则跳过该任务。
    """
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
    """
    构建会话的完整导出数据结构（用于 JSON 导出/备份）。

    包含会话元信息及其所有消息的完整内容。

    参数（均为关键字参数）：
      - session: ChatSession 实例。

    返回：
      - dict: {
            "session": { ... 会话字段 ... },
            "messages": [ ... 所有消息的完整字段 ... ],
            "exported_at": "<ISO-8601 时间戳>"
        }
    """
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
