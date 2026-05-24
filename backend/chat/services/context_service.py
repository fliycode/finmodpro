"""
Chat 上下文组装服务（Context Service）。

类比 SpringBoot：
  - 相当于 @Service 类，负责将多源信息组装为 LLM 可用的消息列表。
  - build_chat_messages() 是把对话历史、长期记忆、检索引用和系统提示词拼接为
    [{"role": "...", "content": "..."}] 的单一入口函数。

上下文信息来源：
  1. FinModPro 系统提示词（平台定位说明）
  2. 会话滚动摘要（rolling_summary）
  3. 最近对话记录（recent messages，最多 N 条）
  4. 长期记忆（通过 LangGraph MemoryStore 语义检索）
  5. RAG 检索引用（citations）
  6. 最终通过 prompt 模板渲染为完整 user 消息
"""

from django.conf import settings

from chat.models import ChatMessage
from chat.services.store import django_memory_store
from llm.services.prompt_service import render_prompt

# FinModPro 平台助手的系统级提示词，定义助手身份和行为准则。
FINMODPRO_SYSTEM_PROMPT = (
    "你是 FinModPro 平台内置的专业金融分析助手，服务于企业财务、风险、知识库和投研分析场景。"
    "当用户询问你是谁、能做什么或平台能力时，明确说明你是 FinModPro 的平台助手。"
    "回答应专业、审慎、结构清晰；不要编造数据或来源。"
    "只有在用户问题与提供的参考资料直接相关时才使用并引用资料。"
)


def _get_positive_int_setting(name, default):
    """
    从 Django settings 中获取正整数配置值。

    如果配置值无效（不存在、非整数、小于等于 0），则返回默认值。

    参数：
      - name: str Django 设置键名。
      - default: int 默认值。

    返回：
      - int: 正整数配置值。
    """
    raw_value = getattr(settings, name, default)
    try:
        return max(int(raw_value), 1)
    except (TypeError, ValueError):
        return default


def _collapse_text(value):
    """
    将文本压缩为单行：去除多余空白，将连续的空白字符替换为单个空格。

    参数：
      - value: str 原始文本。

    返回：
      - str: 压缩后的单行文本。
    """
    return " ".join(str(value or "").split()).strip()


def _format_recent_messages(messages):
    """
    将最近消息列表格式化为上下文文本。

    参数：
      - messages: list[ChatMessage] 消息列表。

    返回：
      - str: 格式化的上下文文本，每行格式为 "- 角色: 内容"。
    """
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
    """
    将长期记忆列表格式化为上下文文本。

    参数：
      - memories: list[MemoryItem|dict] 记忆条目列表。

    返回：
      - str: 格式化的上下文文本，每行格式为 "- 标题: 内容"。
    """
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
    """
    将引用列表格式化为上下文文本。

    参数：
      - citations: list[dict] 引用列表，每条含 document_title / page_label / snippet/window。

    返回：
      - str: 带编号的引用上下文文本，每行格式为 "[N] 文档标题 位置: 摘要"。
    """
    lines = []
    for index, citation in enumerate(citations or [], start=1):
        document_title = citation.get("document_title", "未命名资料")
        page_label = citation.get("page_label") or "未标注位置"
        snippet = _collapse_text(citation.get("window") or citation.get("snippet"))
        lines.append(f"[{index}] {document_title} {page_label}: {snippet}")
    return "\n".join(lines)


def _build_context_sections(*, rolling_summary="", recent_messages=None, memories=None, citations=None):
    """
    将各来源的上下文信息组装为多个段落。

    参数（均为关键字参数）：
      - rolling_summary: str 会话滚动摘要。
      - recent_messages: list[ChatMessage] 最近消息列表。
      - memories: list 长期记忆列表。
      - citations: list[dict] 检索引用列表。

    返回：
      - str: 多个上下文字段的拼接字符串。每个段落以标签开头（"会话摘要:" / "最近对话:" / "长期记忆:" / "参考资料:"）。
        如果某个来源无内容，则对应段落被跳过。
    """
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


def _get_store():
    """
    获取当前活跃的 Memory Store 实例。

    如果在 LangGraph 节点中运行，返回图注入的 store；否则返回模块级单例 django_memory_store。

    返回：
      - BaseStore: 活跃的 Memory Store 实例。
    """
    try:
        from langgraph.config import get_store
        return get_store()
    except Exception:
        return django_memory_store


def _load_memories(*, user, question, dataset_id=None, limit=5):
    """
    通过 LangGraph Store 加载与当前问题相关的长期记忆。

    先从用户的全局命名空间中检索，如果提供了 dataset_id，再额外检索数据集命名空间。
    两次结果合并后返回。

    参数（均为关键字参数）：
      - user: User 模型实例。
      - question: str 用户提问（用于语义匹配）。
      - dataset_id: str|int|None 数据集 ID。
      - limit: int 返回条数上限，默认 5。

    返回：
      - list[dict]: 记忆条目的 value 列表（每个 value 是包含 title/content/memory_type 等的字典）。
    """
    store = _get_store()
    user_ns = ("memories", str(user.id))
    items = store.search(user_ns, query=question, limit=limit)

    if dataset_id not in (None, ""):
        ds_ns = ("memories", str(user.id), "dataset", str(dataset_id))
        items = items + store.search(ds_ns, query=question, limit=limit)

    return [item.value for item in items]


def build_chat_messages(*, question, session=None, citations=None, filters=None):
    """
    构建 LLM 对话所需的消息列表（系统提示词 + 用户消息）。

    这是上下文组装的单一入口。根据是否有会话上下文，决定是否加载最近消息和长期记忆。
    最后通过 render_prompt 模板将 question + 上下文渲染为最终的 user 消息。

    类比 SpringBoot：
      - 相当于 @Service 方法，将多个数据源（会话历史、记忆、检索结果）聚合为 LLM 所需的输入格式。

    参数（均为关键字参数）：
      - question: str 用户提问文本（必填）。
      - session: ChatSession | None 关联的会话对象。
      - citations: list[dict] 检索引用列表。
      - filters: dict 上下文过滤条件（用于提取 dataset_id 加载数据集记忆）。

    返回：
      - list[dict]: 消息列表，格式为 [{"role": "system", "content": "..."}, {"role": "user", "content": "..."}]。
        如果无上下文信息，直接返回 [system_prompt, question]。
    """
    citations = citations or []

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
        memories = _load_memories(
            user=session.user,
            question=question,
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
        return [
            {"role": "system", "content": FINMODPRO_SYSTEM_PROMPT},
            {"role": "user", "content": question},
        ]

    prompt = render_prompt(
        "chat/answer.txt",
        question=question,
        context=context,
    )
    return [
        {"role": "system", "content": FINMODPRO_SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]
