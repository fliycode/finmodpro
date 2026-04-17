from django.conf import settings

from chat.models import ChatMessage
from chat.services.memory_service import search_memories
from llm.services.prompt_service import render_prompt


def _get_positive_int_setting(name, default):
    raw_value = getattr(settings, name, default)
    try:
        return max(int(raw_value), 1)
    except (TypeError, ValueError):
        return default


def _collapse_text(value):
    return " ".join(str(value or "").split()).strip()


def _format_recent_messages(messages):
    role_labels = {
        ChatMessage.ROLE_USER: "用户",
        ChatMessage.ROLE_ASSISTANT: "助手",
        ChatMessage.ROLE_SYSTEM: "系统",
    }
    lines = []
    for message in messages:
        content = _collapse_text(message.content)
        if not content:
            continue
        lines.append(f"- {role_labels.get(message.role, message.role)}: {content}")
    return "\n".join(lines)


def _format_memories(memories):
    lines = []
    for memory in memories:
        if isinstance(memory, dict):
            title = _collapse_text(memory.get("title"))
            content = _collapse_text(memory.get("content"))
        else:
            title = _collapse_text(getattr(memory, "title", ""))
            content = _collapse_text(getattr(memory, "content", ""))
        if not (title or content):
            continue
        if title and content:
            lines.append(f"- {title}: {content}")
        else:
            lines.append(f"- {title or content}")
    return "\n".join(lines)


def _format_citations(citations):
    lines = []
    for index, citation in enumerate(citations or [], start=1):
        document_title = citation.get("document_title", "未命名资料")
        page_label = citation.get("page_label") or "未标注位置"
        snippet = _collapse_text(citation.get("snippet"))
        lines.append(f"[{index}] {document_title} {page_label}: {snippet}")
    return "\n".join(lines)


def _build_context_sections(*, rolling_summary="", recent_messages=None, memories=None, citations=None):
    sections = []
    normalized_summary = _collapse_text(rolling_summary)
    if normalized_summary:
        sections.append(f"会话摘要:\n{normalized_summary}")

    recent_block = _format_recent_messages(recent_messages or [])
    if recent_block:
        sections.append(f"最近对话:\n{recent_block}")

    memory_block = _format_memories(memories or [])
    if memory_block:
        sections.append(f"长期记忆:\n{memory_block}")

    citation_block = _format_citations(citations or [])
    if citation_block:
        sections.append(f"参考资料:\n{citation_block}")

    return "\n\n".join(sections)


def build_chat_messages(*, question, session=None, citations=None, filters=None):
    citations = citations or []
    if session is None and not citations:
        return [{"role": "user", "content": question}]

    recent_messages = []
    memories = []
    if session is not None:
        recent_message_limit = _get_positive_int_setting("CHAT_CONTEXT_RECENT_MESSAGES", 8)
        recent_messages = list(
            reversed(
                list(
                    session.messages.filter(status=ChatMessage.STATUS_COMPLETE).order_by(
                        "-sequence", "-id"
                    )[:recent_message_limit]
                )
            )
        )
        dataset_id = (filters or {}).get("dataset_id")
        memory_limit = _get_positive_int_setting("CHAT_MEMORY_RESULT_LIMIT", 5)
        memories = search_memories(
            user=session.user,
            query=question,
            dataset_id=dataset_id,
            limit=memory_limit,
        )

    context = _build_context_sections(
        rolling_summary=getattr(session, "rolling_summary", ""),
        recent_messages=recent_messages,
        memories=memories,
        citations=citations,
    )
    if not context:
        return [{"role": "user", "content": question}]

    prompt = render_prompt(
        "chat/answer.txt",
        question=question,
        context=context,
    )
    return [{"role": "user", "content": prompt}]
