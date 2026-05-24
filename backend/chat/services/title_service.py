"""
Chat 会话标题自动生成服务（Title Service）。

类比 SpringBoot：
  - 相当于 @Service 类，负责通过 LLM 自动为会话生成简洁的中文标题。
  - 通过 Celery 异步任务调用 generate_session_title() 函数。

标题生成策略：
  1. 手动标题：如果 title_source == MANUAL，保持用户设定的标题不变。
  2. 已有 AI 标题：如果标题已由 AI 生成且状态为 READY，不重新生成。
  3. 自动生成条件：会话中恰好有 1 条已完成用户消息 + 至少 1 条已完成 assistant 回复。
  4. LLM 调用：取前 4 条消息作为上下文，让 LLM 生成不超过 12 个汉字的标题。
  5. 回退：如果 LLM 生成失败，使用第一条用户消息截断作为标题。

标题截断规则：
  - 最长 32 个字符（ChatSession.title 字段最大长度与 TITLE_MAX_LENGTH 取较小值）。
  - 超过长度时用 "..." 替代末尾 3 个字符。
"""

from chat.models import ChatMessage, ChatSession
from llm.services.runtime_service import get_chat_provider

# AI 生成标题的最大长度（汉字/字符数）
TITLE_MAX_LENGTH = 32


def _truncate_title(value, max_length):
    """
    截断标题文本到指定长度，超出部分用 "..." 替代。

    参数：
      - value: str 原始标题文本。
      - max_length: int 最大长度。

    返回：
      - str: 截断后的标题。格式：text... (保留 max_length - 3 个字符 + "...")
    """
    normalized = " ".join(str(value or "").split()).strip()
    if len(normalized) <= max_length:
        return normalized
    if max_length <= 3:
        return normalized[:max_length]
    return f"{normalized[: max_length - 3].rstrip()}..."


def _clean_generated_title(value):
    """
    清洗 LLM 生成的标题：去除引号、标点和首尾空白。

    参数：
      - value: str LLM 原始输出。

    返回：
      - str: 清洗并截断后的标题。空文本返回空字符串。
    """
    normalized = " ".join(str(value or "").split()).strip()
    normalized = normalized.strip("\"'“”'`#：:，,。. ")
    if not normalized:
        return ""
    return _truncate_title(normalized, TITLE_MAX_LENGTH)


def _build_title_messages(session):
    """
    构建发送给 LLM 的标题生成消息列表。

    取会话中前 4 条已完成消息作为上下文，拼接为对话摘要文本。

    参数：
      - session: ChatSession 实例。

    返回：
      - list[dict]: 消息列表，包含 system（生成指令）和 user（对话内容）两条消息。
    """
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
                "请根据用户的提问意图生成一个简洁中文标题，最多 12 个汉字，"
                "标题应概括用户想做什么，不要照抄助手的回答内容，"
                "不要添加引号、标点或解释。"
            ),
        },
        {
            "role": "user",
            "content": f"对话内容：\n{transcript}\n\n只输出标题：",
        },
    ]


def _generate_ai_title(session):
    """
    调用 LLM 生成 AI 标题。

    参数：
      - session: ChatSession 实例。

    返回：
      - str: 清洗后的 AI 标题。LLM 调用失败时返回空字符串。
    """
    try:
        title = get_chat_provider().chat(
            messages=_build_title_messages(session),
            options={"temperature": 0.2, "max_tokens": 24},
        ).content
    except Exception:
        return ""
    return _clean_generated_title(title)


def generate_session_title(*, session_id):
    """
    为指定会话生成/更新标题（Celery 任务入口）。

    类比 SpringBoot：
      - 相当于 @Async 方法，由 Celery Beat 或在每次问答完成后自动触发。

    策略：
      1. 手动标题 -> 保持不变（仅更新 title_status 为 READY 如果需要）。
      2. 非 AI 来源且非默认标题 -> 标记为 READY。
      3. AI 来源且状态已 READY 且非默认标题 -> 不重新生成。
      4. 条件满足时（1 条用户消息 + 至少 1 条助手回复）-> LLM 生成新标题。

    参数（均为关键字参数）：
      - session_id: int 会话 ID。

    返回：
      - str|None: 最终标题文本；会话不存在时返回 None。
    """
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
