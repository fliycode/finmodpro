"""
Chat 会话摘要服务（Summary Service）。

类比 SpringBoot：
  - 相当于 @Service 类，负责会话的滚动摘要（rolling summary）计算。
  - 通过 Celery 异步任务调用 update_session_summary() 函数。

摘要策略：
  - 当会话中已完成消息数达到 CHAT_SUMMARY_TRIGGER_MESSAGES（默认 6 条）时触发更新。
  - 取末尾 N 条消息（最近触发数），将用户和助手的发言以 "角色: 内容" 格式用 " | " 拼接。
  - 通过 summary_updated_through_message_id 避免对同一批消息重复计算。
  - 使用 select_for_update() 确保在高并发下不会产生竞态条件。

类比数据库的物化视图（Materialized View）维护策略：
  - 增量更新，仅在新增消息时计算，不是全量重建。
"""

from django.conf import settings
from django.db import transaction

from chat.models import ChatMessage, ChatSession


def _get_summary_trigger():
    """
    获取触发摘要更新的消息数阈值。

    从 settings.CHAT_SUMMARY_TRIGGER_MESSAGES 读取，无效值时回退到默认值 6。

    返回：
      - int: 正整数阈值。
    """
    raw_value = getattr(settings, "CHAT_SUMMARY_TRIGGER_MESSAGES", 6)
    try:
        return max(int(raw_value), 1)
    except (TypeError, ValueError):
        return 6


def _collapse_text(value):
    """
    将文本压缩为单行字符串。

    参数：
      - value: str 原始文本。

    返回：
      - str: 压缩后的单行文本。
    """
    return " ".join(str(value or "").split()).strip()


def update_session_summary(*, session_id):
    """
    更新指定会话的滚动摘要。

    使用 select_for_update() 行锁防止并发写入冲突。

    逻辑：
      1. 如果会话不存在或无消息，返回当前摘要
      2. 如果最近消息的 ID 未超过上次更新位置，跳过（无需更新）
      3. 如果已完成消息数未达到触发阈值，跳过
      4. 取最近的 N 条消息拼接为摘要文本

    类比 SpringBoot：
      - 相当于 @Transactional(isolation = SERIALIZABLE) 的 @Service 方法，
        使用悲观锁确保数据一致性。

    参数（均为关键字参数）：
      - session_id: int 会话 ID。

    返回：
      - str|None: 更新后的滚动摘要文本；会话不存在时返回 None。
    """
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
