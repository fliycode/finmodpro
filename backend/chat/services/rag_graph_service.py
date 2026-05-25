"""
Chat RAG 图谱服务（RAG Graph Service）。

类比 SpringBoot：
  - 相当于 @Service 类，使用 LangGraph 构建有状态的 RAG 处理流水线。
  - StateGraph 类似于 Spring StateMachine 或流程编排引擎（如 Camunda），
    通过有向图（DAG）定义节点和条件边来编排 RAG 的处理步骤。

RAG 图谱流程（Graph Nodes & Edges）：
  START
    |
  [route] ──(direct)──> [direct_answer_context] ──> END
    |
    (retrieve)
    |
  [rewrite_query] ──> [retrieve_and_merge] ──> [score_filter]
                                                  |
                          ┌──(有结果)──> [build_retrieval_context] ──> END
                          |
                          └──(无结果)──> [empty_retrieval_context] ──> END

节点说明：
  - route: LLM 驱动的意图路由（regex 预检查 + LLM 分类），判断走"检索"还是"直接回答"
  - rewrite_query: 用 LLM 重写问题为更优的检索查询
  - retrieve_and_merge: 并行检索 + 重排序合并
  - score_filter: 按相关性阈值过滤结果
  - build_retrieval_context: 将检索结果组装为带引用的上下文
  - empty_retrieval_context: 无检索结果时的回落上下文
  - direct_answer_context: 直接回答（问候语、自我介绍等不查知识库的轻量对话）

该模块核心是构建 RAG 有向图，对外提供 prepare_chat_payload() 和
prepare_chat_payload_streaming() 两个入口函数。
"""

import json
import logging
import re
import time
from typing import TypedDict

from django.conf import settings
from langgraph.config import get_stream_writer
from langgraph.graph import END, START, StateGraph
from langgraph.types import RetryPolicy

from chat.services.context_service import build_chat_messages
from chat.services.session_service import normalize_context_filters
from chat.services.store import django_memory_store
from rag.services.retrieval_backend_service import retrieve_chat_context
from rag.services.rerank_service import rerank_with_variants
from rag.services.retrieval_service import build_retrieval_response

logger = logging.getLogger(__name__)

# 回答中引用的最大条数
MAX_CHAT_CITATIONS = 3


def _should_retry_retrieval(exc: Exception) -> bool:
    """
    判断检索失败时是否应重试。

    对 Milvus 连接异常等瞬时性错误进行重试；对程序错误（ValueError, TypeError）不重试。

    参数：
      - exc: Exception 检索过程中抛出的异常。

    返回：
      - bool: True 表示应当重试，False 表示不应重试。
    """
    from pymilvus.exceptions import MilvusException
    if isinstance(exc, (ConnectionError, MilvusException)):
        return True
    if isinstance(exc, (ValueError, TypeError, RuntimeError, OSError)):
        return False
    return True


# 检索节点的重试策略：最多 2 次，退避因子 1.0，初始间隔 0.5s，启用抖动
_RETRIEVAL_RETRY = RetryPolicy(
    max_attempts=2,
    backoff_factor=1.0,
    initial_interval=0.5,
    jitter=True,
    retry_on=_should_retry_retrieval,
)


def retrieve_chat_context_results(*, query, filters=None, top_k=None, query_variants=None):
    """
    调用检索后端服务获取上下文文档结果。

    参数（均为关键字参数）：
      - query: str 检索查询文本。
      - filters: dict|None 检索过滤条件。
      - top_k: int|None 返回条数，默认 5。
      - query_variants: list[str]|None 多查询变体（用于并行召回）。

    返回：
      - list[dict]: 检索结果列表，每条包含文档片段、相关性分数等。
    """
    return retrieve_chat_context(
        query=query,
        filters=filters,
        top_k=top_k or 5,
        query_variants=query_variants,
    )

# --- 路由规则的模式匹配列表 ---

# 直接助手意图：问候语、自我介绍、平台询问等
_DIRECT_ASSISTANT_PATTERNS = (
    "你是谁",
    "你是什么",
    "这是什么平台",
    "是什么平台",
    "什么平台",
    "当前平台",
    "这个平台",
    "介绍一下你",
    "介绍一下自己",
    "你能做什么",
    "你可以做什么",
    "who are you",
    "what are you",
)
# 约束性回复词：表明用户想要简短/有限的回答，不需要检索
_CONSTRAINED_RESPONSE_PATTERNS = (
    "只回复",
    "只返回",
    "只说",
    "一句话",
    "两句话",
    "一个词",
    "两个字",
    "四个字",
    "不要解释",
    "不用解释",
)

# 用于从 LLM 重写输出中提取 JSON 的正则模式
_JSON_OBJECT_PATTERN = re.compile(r"\{.*\}", re.DOTALL)
_FENCED_JSON_PATTERN = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL | re.IGNORECASE)


class ChatRagState(TypedDict, total=False):
    """
    RAG 图谱的共享状态定义。

    类比 SpringBoot：
      - 相当于状态机中的 Context 对象，在图的各节点间传递和累积数据。

    字段：
      - question: str 用户原始问题
      - filters: dict 前端传入的过滤条件
      - top_k: int 检索返回条数
      - session: ChatSession|None 当前会话
      - provider: object LLM 提供商实例
      - resolved_filters: dict 合并后的最终过滤条件
      - route: str 路由决策（retrieve / direct）
      - route_guard: str 路由决策依据（direct_assistant_intent / context_filters_present 等）
      - rewritten_query: str 重写后的检索查询
      - query_variants: list[str] 查询变体列表
      - retrieval_results: list[dict] 检索结果
      - citations: list[dict] 引用列表
      - answer_mode: str 回答模式（cited / fallback / direct）
      - messages: list[dict] 最终发送给 LLM 的消息
    """
    question: str
    filters: dict
    top_k: int
    session: object
    provider: object
    resolved_filters: dict
    route: str
    route_guard: str
    rewritten_query: str
    query_variants: list
    retrieval_results: list
    citations: list
    answer_mode: str
    messages: list


def _build_answer_notice(answer_mode):
    """
    根据回答模式生成用户提示信息。

    参数：
      - answer_mode: str 回答模式。

    返回：
      - str|None: fallback 模式下返回"当前回答未命中知识库引用..."提示；其他模式返回 None。
    """
    if answer_mode != "fallback":
        return None
    return "当前回答未命中知识库引用，仅基于通用模型能力生成，请注意甄别。"


def _normalize_question_text(question):
    """
    将问题文本标准化为小写单行，用于意图匹配。

    参数：
      - question: str 原始问题。

    返回：
      - str: 标准化后的小写文本。
    """
    return " ".join(str(question or "").strip().lower().split())


def _has_direct_assistant_intent(question):
    """
    检测问题是否为"直接助手意图"（问候、自我介绍等）。

    参数：
      - question: str 用户问题。

    返回：
      - bool: True 表示问题属于直接助手意图，无需检索。
    """
    normalized = _normalize_question_text(question)
    return any(pattern in normalized for pattern in _DIRECT_ASSISTANT_PATTERNS)


def _has_constrained_response_intent(question):
    """
    检测问题是否包含"约束性回复"意图（要求简短回答，不需要检索）。

    参数：
      - question: str 用户问题。

    返回：
      - bool: True 表示属于约束性回复，应走直接回答路径。
    """
    normalized = _normalize_question_text(question)
    if not normalized:
        return False
    return any(pattern in normalized for pattern in _CONSTRAINED_RESPONSE_PATTERNS)


def _parse_json_candidate(raw_text):
    """
    从 LLM 原始输出中提取 JSON 对象。

    支持三种格式：
      1. 代码块包裹的 JSON（```json ... ```）
      2. 可直接解析的 JSON 对象/数组
      3. 嵌入文本中的 JSON 对象（正则匹配 { ... }）

    参数：
      - raw_text: str LLM 原始输出。

    返回：
      - dict|list: 解析后的 JSON 数据。
    """
    text = str(raw_text or "").strip()
    fenced_match = _FENCED_JSON_PATTERN.search(text)
    if fenced_match:
        text = fenced_match.group(1).strip()
    if (text.startswith("{") and text.endswith("}")) or (text.startswith("[") and text.endswith("]")):
        candidate = text
    else:
        match = _JSON_OBJECT_PATTERN.search(text)
        candidate = match.group(0) if match else text
    return json.loads(candidate)


def _normalize_query_variants(*queries, limit=None):
    """
    标准化查询变体列表：去重、去空白、截断到 limit。

    参数：
      - *queries: 一个或多个查询（可以是 str 或 list）。
      - limit: int|None 返回的最大变体数，默认取 settings.RAG_MULTI_QUERY_VARIANT_COUNT。

    返回：
      - list[str]: 标准化后的唯一查询变体列表。
    """
    resolved_limit = limit
    if resolved_limit is None:
        resolved_limit = getattr(settings, "RAG_MULTI_QUERY_VARIANT_COUNT", 1)
    try:
        resolved_limit = max(int(resolved_limit or 1), 1)
    except (TypeError, ValueError):
        resolved_limit = 1
    seen = set()
    normalized = []
    for candidate in queries:
        if isinstance(candidate, list):
            for item in candidate:
                value = str(item or "").strip()
                if not value or value in seen:
                    continue
                seen.add(value)
                normalized.append(value)
        else:
            value = str(candidate or "").strip()
            if not value or value in seen:
                continue
            seen.add(value)
            normalized.append(value)
    return normalized[:resolved_limit]


def _extract_query_variants(parsed, fallback_query, *, limit=None):
    """
    从 LLM 重写结果的 JSON 中提取查询变体。

    参数：
      - parsed: dict LLM 返回的 JSON 对象。
      - fallback_query: str 回退用的原始问题（当 LLM 返回无效时）。
      - limit: int|None 返回的最大变体数。

    返回：
      - list[str]: 查询变体列表。
    """
    if not isinstance(parsed, dict):
        return _normalize_query_variants(fallback_query, limit=limit)
    raw_variants = parsed.get("query_variants") or parsed.get("queries") or parsed.get("variants") or []
    return _normalize_query_variants(
        parsed.get("rewritten_query") or fallback_query,
        raw_variants,
        limit=limit,
    )


def _chat_query_variant_limit():
    """
    获取聊天场景下的查询变体数量上限。

    返回：
      - int: 正整数配置值，默认 1。
    """
    raw_value = getattr(
        settings,
        "CHAT_RAG_QUERY_VARIANT_COUNT",
        getattr(settings, "RAG_MULTI_QUERY_VARIANT_COUNT", 1),
    )
    try:
        return max(int(raw_value or 1), 1)
    except (TypeError, ValueError):
        return 1


def _chat_retrieval_top_k(requested_top_k):
    """
    计算聊天场景下实际的检索返回条数。

    公式: max(requested_top_k * CHAT_RAG_RETRIEVAL_TOP_K_MULTIPLIER, CHAT_RAG_RETRIEVAL_TOP_K_FLOOR)
    这样可以检索比需求更多的结果，供后续重排序和评分过滤。

    参数：
      - requested_top_k: int 前端请求的条数。

    返回：
      - int: 实际的检索条数。
    """
    try:
        normalized_top_k = max(int(requested_top_k), 1)
    except (TypeError, ValueError):
        normalized_top_k = 1
    try:
        multiplier = max(int(getattr(settings, "CHAT_RAG_RETRIEVAL_TOP_K_MULTIPLIER", 2) or 2), 1)
    except (TypeError, ValueError):
        multiplier = 2
    try:
        floor = max(int(getattr(settings, "CHAT_RAG_RETRIEVAL_TOP_K_FLOOR", 8) or 8), 1)
    except (TypeError, ValueError):
        floor = 8
    return max(normalized_top_k * multiplier, floor)


def _numeric_score(item, key):
    """
    从检索结果条目中安全提取数值评分。

    参数：
      - item: dict 检索结果条目。
      - key: str 评分字段名。

    返回：
      - float|None: 数值评分，无效值时返回 None。
    """
    try:
        return float(item.get(key))
    except (TypeError, ValueError):
        return None


def _best_relevance_score(item):
    """
    获取检索结果的最佳相关性评分。

    从可选字段 rerank_score > score > keyword_score > vector_score 中选取最大值。

    参数：
      - item: dict 检索结果条目。

    返回：
      - float|None: 最佳评分，所有字段都无效时返回 None。
    """
    scores = [
        _numeric_score(item, "rerank_score"),
        _numeric_score(item, "score"),
        _numeric_score(item, "keyword_score"),
        _numeric_score(item, "vector_score"),
    ]
    numeric_scores = [score for score in scores if score is not None]
    if not numeric_scores:
        return None
    return max(numeric_scores)


def _score_threshold():
    """
    获取检索结果的评分过滤阈值。

    返回：
      - float: 阈值，默认 0.12。低于此值的结果被过滤掉。
    """
    return float(getattr(settings, "RAG_SCORE_FILTER_THRESHOLD", 0.12))


def _select_relevant_results(results, *, limit=MAX_CHAT_CITATIONS):
    """
    按评分阈值过滤检索结果，并截断到指定上限。

    参数：
      - results: list[dict] 检索结果列表。
      - limit: int|None 返回条数上限，None 表示不截断。

    返回：
      - list[dict]: 过滤和截断后的结果列表。
    """
    threshold = _score_threshold()
    relevant = []
    for item in results:
        score = _best_relevance_score(item)
        if score is not None and score < threshold:
            continue
        relevant.append(item)
    if limit is None:
        return relevant
    return relevant[:limit]


# --- 图节点（Graph Nodes） ---


def _emit_step(data: dict):
    """
    通过 LangGraph stream writer 安全地推送一个步骤事件。

    在流式模式下，此函数将步骤进度发送给 SSE 接收端。
    如果不在流式上下文中（如 invoke 模式），此函数静默忽略。

    参数：
      - data: dict 步骤数据（如 {"step": "route", "route": "retrieve"}）。
    """
    try:
        get_stream_writer()(data)
    except Exception:
        pass


def _classify_intent_with_llm(question, provider):
    """
    使用 LLM 判断用户问题是否需要从知识库检索。

    轻量级二分类：retrieve（检索）或 direct（直接回答）。
    temperature=0 保证确定性，max_tokens=64 降低成本。

    参数：
      - question: str 用户问题。
      - provider: object LLM 提供商实例。

    返回：
      - tuple[str, str]: (route, route_guard)，失败时兜底返回 ("retrieve", "llm_router_fallback")。
    """
    prompt = [
        {
            "role": "system",
            "content": (
                "你是查询路由器。判断用户问题是否需要从知识库检索资料来回答。"
                "输出严格 JSON：{\"route\": \"retrieve\", \"reason\": \"...\"} "
                "或 {\"route\": \"direct\", \"reason\": \"...\"}，不要输出额外文本。\n"
                "需要检索(retrieve)：涉及具体数据、事实、文档内容、公司信息、金融指标、业务规则等需要查资料的问题。\n"
                "直接回答(direct)：问候闲聊、通用概念解释、创作生成、个人观点建议等无需查资料的问题。"
            ),
        },
        {"role": "user", "content": question},
    ]
    try:
        raw_output = provider.chat(
            messages=prompt,
            options={"temperature": 0, "max_tokens": 64},
        ).content
        parsed = _parse_json_candidate(raw_output)
        if isinstance(parsed, dict) and parsed.get("route") in ("retrieve", "direct"):
            return parsed["route"], "llm_router"
    except Exception:
        logger.exception("LLM routing failed; defaulting to retrieve")
    return "retrieve", "llm_router_fallback"


def _route_by_llm(state: ChatRagState):
    """
    图节点：LLM 驱动的问题路由。

    优先级：regex 预检查（零成本拦截明显不需检索的问候/约束意图）
    → 上下文过滤器 → LLM 意图分类 → 失败兜底检索。

    参数：
      - state: ChatRagState 当前图状态。

    返回：
      - dict: 包含 route 和 route_guard 的更新状态。
    """
    question = state["question"]
    resolved_filters = state.get("resolved_filters") or {}
    if _has_direct_assistant_intent(question):
        route = "direct"
        route_guard = "direct_assistant_intent"
    elif _has_constrained_response_intent(question):
        route = "direct"
        route_guard = "constrained_response_intent"
    elif resolved_filters:
        route = "retrieve"
        route_guard = "context_filters_present"
    else:
        route, route_guard = _classify_intent_with_llm(question, state["provider"])
    logger.info(
        "chat rag route",
        extra={"question": question, "route": route, "route_guard": route_guard},
    )
    _emit_step({"step": "route", "route": route, "route_guard": route_guard})
    return {"route": route, "route_guard": route_guard}


def _rewrite_query(state: ChatRagState):
    """
    图节点：使用 LLM 重写查询以优化检索效果。

    将用户自然语言问题改写为更适合向量检索的查询格式，并生成多个查询变体用于并行召回。
    如果 LLM 调用或 JSON 解析失败，退回使用原始问题。

    参数：
      - state: ChatRagState 当前图状态（需包含 question 和 provider）。

    返回：
      - dict: 包含 rewritten_query 和 query_variants 的更新状态。
    """
    question = state["question"]
    provider = state["provider"]
    max_query_variants = _chat_query_variant_limit()
    prompt = [
        {
            "role": "system",
            "content": (
                "你是 FinModPro 的检索查询重写器。"
                "请把用户问题改写成更适合检索金融知识库的查询，保留关键实体、财务指标、时间范围和文档线索。"
                f"同时给出最多 {max_query_variants} 条高保真检索式，用于并行召回。"
                "输出严格 JSON："
                "{\"rewritten_query\":\"...\",\"query_variants\":[\"...\",\"...\"]}，"
                "不要输出额外文本。"
            ),
        },
        {"role": "user", "content": question},
    ]
    try:
        raw_output = provider.chat(messages=prompt, options={"temperature": 0, "max_tokens": 64}).content
    except Exception:
        logger.exception("chat rag rewrite provider failed; falling back to original question")
        rewritten_query = question
        query_variants = _normalize_query_variants(question, limit=max_query_variants)
    else:
        try:
            parsed = _parse_json_candidate(raw_output)
            if not isinstance(parsed, dict):
                raise ValueError("rewrite response is not a JSON object")
            rewritten_query = str(parsed.get("rewritten_query") or "").strip() or question
            query_variants = _extract_query_variants(parsed, rewritten_query, limit=max_query_variants)
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            logger.warning(
                "chat rag rewrite returned invalid JSON; falling back to original question",
                extra={"error": str(exc)},
            )
            rewritten_query = question
            query_variants = _normalize_query_variants(question, limit=max_query_variants)
    logger.info(
        "chat rag rewrite",
        extra={
            "question": question,
            "rewritten_query": rewritten_query,
            "query_variants": query_variants,
        },
    )
    _emit_step({"step": "rewrite_query", "rewritten_query": rewritten_query, "query_variants": query_variants})
    return {
        "rewritten_query": rewritten_query,
        "query_variants": query_variants,
    }


def _retrieve_and_merge(state: ChatRagState):
    """
    图节点：执行向量检索 + 重排序合并。

    根据查询变体进行多路检索，将结果合并后调用 rerank 服务重排序。
    使用放大后的检索窗口（top_k * multiplier）保证候选池充足。

    参数：
      - state: ChatRagState 当前图状态。

    返回：
      - dict: 包含 retrieval_results 的更新状态。
    """
    rewritten_query = state.get("rewritten_query") or state["question"]
    query_variants = state.get("query_variants") or _normalize_query_variants(
        rewritten_query,
        limit=_chat_query_variant_limit(),
    )
    requested_top_k = int(state["top_k"])
    retrieval_top_k = _chat_retrieval_top_k(requested_top_k)
    candidate_limit = retrieval_top_k

    raw_results = retrieve_chat_context_results(
        query=rewritten_query,
        filters=state.get("resolved_filters") or {},
        top_k=retrieval_top_k,
        query_variants=query_variants,
    )
    reranked = rerank_with_variants(
        raw_results,
        query_variants=query_variants,
        fallback_query=rewritten_query,
    )
    retrieval_results = _select_relevant_results(reranked, limit=candidate_limit)
    logger.info(
        "chat rag retrieve",
        extra={
            "question": state["question"],
            "rewritten_query": rewritten_query,
            "query_variants": query_variants,
            "top_k": retrieval_top_k,
            "retrieved_count": len(retrieval_results),
            "retrieval_source": "llamaindex" if raw_results else "none",
        },
    )
    _emit_step({"step": "retrieve", "retrieved_count": len(retrieval_results)})
    return {"retrieval_results": retrieval_results}


def _score_filter(state: ChatRagState):
    """
    图节点：按评分阈值二次过滤检索结果。

    参数：
      - state: ChatRagState 当前图状态。

    返回：
      - dict: 包含过滤后 retrieval_results 的更新状态。
    """
    results = state.get("retrieval_results") or []
    filtered = _select_relevant_results(results)
    logger.info(
        "chat rag score_filter",
        extra={
            "question": state["question"],
            "input_count": len(results),
            "filtered_count": len(filtered),
            "threshold": _score_threshold(),
        },
    )
    _emit_step({"step": "score_filter", "input_count": len(results), "filtered_count": len(filtered), "threshold": _score_threshold()})
    return {"retrieval_results": filtered}


def _build_retrieval_context(state: ChatRagState):
    """
    图节点：将检索结果构建为回答上下文（包含引用）。

    根据检索结果生成 citations 和 messages，确定 answer_mode：
      - 有引用 -> "cited"
      - 无引用 -> "fallback"

    参数：
      - state: ChatRagState 当前图状态。

    返回：
      - dict: 包含 citations / answer_mode / messages / retrieval_results 的更新状态。
    """
    retrieval_results = state.get("retrieval_results") or []
    citations = build_retrieval_response(
        query=state["question"],
        results=retrieval_results,
    )["citations"]
    answer_mode = "cited" if citations else "fallback"
    _emit_step({"step": "build_context", "citation_count": len(citations), "answer_mode": answer_mode})
    return {
        "retrieval_results": retrieval_results,
        "citations": citations,
        "answer_mode": answer_mode,
        "messages": build_chat_messages(
            session=state.get("session"),
            question=state["question"],
            citations=citations,
            filters=state["resolved_filters"],
        ),
    }


def _direct_answer_context(state: ChatRagState):
    """
    图节点：构建直接回答上下文（无需检索）。

    用于问候语、自我介绍等不需要知识库检索的问题。

    参数：
      - state: ChatRagState 当前图状态。

    返回：
      - dict: 包含空检索结果、空引用、"direct" 回答模式和最终消息的更新状态。
    """
    _emit_step({"step": "direct_context", "answer_mode": "direct"})
    return {
        "retrieval_results": [],
        "citations": [],
        "answer_mode": "direct",
        "messages": build_chat_messages(
            session=state.get("session"),
            question=state["question"],
            citations=[],
            filters=state.get("resolved_filters", {}),
        ),
    }


def _route_after_router(state: ChatRagState):
    """
    条件边决策函数：路由节点后的路径选择。

    参数：
      - state: ChatRagState 当前图状态。

    返回：
      - str: "rewrite_query"（进入检索流程）或 "direct_answer_context"（直接回答）。
    """
    return "rewrite_query" if state.get("route") == "retrieve" else "direct_answer_context"


def _route_after_score_filter(state: ChatRagState):
    """
    条件边决策函数：评分过滤节点后的路径选择。

    参数：
      - state: ChatRagState 当前图状态。

    返回：
      - str: "build_retrieval_context"（有相关结果）或 "empty_retrieval_context"（无结果）。
    """
    results = state.get("retrieval_results") or []
    if results:
        return "build_retrieval_context"
    return "empty_retrieval_context"


def _empty_retrieval_context(state: ChatRagState):
    """
    图节点：检索无结果时的回落上下文。

    与 _build_retrieval_context 类似，但 answer_mode 固定为 "fallback"。

    参数：
      - state: ChatRagState 当前图状态。

    返回：
      - dict: 包含 fallback 模式和空引用消息的更新状态。
    """
    _emit_step({"step": "build_context", "citation_count": 0, "answer_mode": "fallback"})
    return {
        "retrieval_results": [],
        "citations": [],
        "answer_mode": "fallback",
        "messages": build_chat_messages(
            session=state.get("session"),
            question=state["question"],
            citations=[],
            filters=state.get("resolved_filters", {}),
        ),
    }


def _build_rag_graph():
    """
    构建并编译 RAG 有向图。

    类比 SpringBoot：
      - 相当于定义状态机的状态迁移配置（@Configuration + StateMachineBuilder）。
      - 图编译后返回一个可执行的 CompiledGraph 实例。

    图结构（DAG）：
      START -> route -> (conditional) -> rewrite_query | direct_answer_context
      rewrite_query -> retrieve_and_merge -> score_filter -> (conditional)
        -> build_retrieval_context | empty_retrieval_context
      build_retrieval_context / empty_retrieval_context / direct_answer_context -> END

    返回：
      - CompiledGraph: 编译后的可执行 RAG 图，挂载了 django_memory_store 作为长期记忆后端。
    """
    graph = StateGraph(ChatRagState)
    graph.add_node("route", _route_by_llm)
    graph.add_node("rewrite_query", _rewrite_query)
    graph.add_node("retrieve_and_merge", _retrieve_and_merge, retry_policy=_RETRIEVAL_RETRY)
    graph.add_node("score_filter", _score_filter)
    graph.add_node("build_retrieval_context", _build_retrieval_context)
    graph.add_node("empty_retrieval_context", _empty_retrieval_context)
    graph.add_node("direct_answer_context", _direct_answer_context)
    graph.add_edge(START, "route")
    graph.add_conditional_edges(
        "route",
        _route_after_router,
        {
            "rewrite_query": "rewrite_query",
            "direct_answer_context": "direct_answer_context",
        },
    )
    graph.add_edge("rewrite_query", "retrieve_and_merge")
    graph.add_edge("retrieve_and_merge", "score_filter")
    graph.add_conditional_edges(
        "score_filter",
        _route_after_score_filter,
        {
            "build_retrieval_context": "build_retrieval_context",
            "empty_retrieval_context": "empty_retrieval_context",
        },
    )
    graph.add_edge("build_retrieval_context", END)
    graph.add_edge("empty_retrieval_context", END)
    graph.add_edge("direct_answer_context", END)
    return graph.compile(store=django_memory_store)


# 模块级别的 RAG 图单例（编译一次，全局复用）
_RAG_GRAPH = _build_rag_graph()


def prepare_chat_payload(*, question, filters=None, top_k=5, session=None, provider=None, retrieve_fn=None):
    """
    准备发送给 LLM 的完整对话负载（同步模式）。

    调用 RAG 图（invoke 方式）获取最终的消息列表、引用和回答模式等信息。

    类比 SpringBoot：
      - 相当于 @Service 方法，调用状态机（图）获取编排结果。

    参数（均为关键字参数）：
      - question: str 用户问题（必填）。
      - filters: dict 上下文过滤条件（可选）。
      - top_k: int 检索返回条数，默认 5。
      - session: ChatSession|None 关联会话。
      - provider: object LLM 提供商实例。
      - retrieve_fn: 保留参数（未使用）。

    返回：
      - dict: 包含 question / query / query_variants / messages / citations /
              answer_mode / answer_notice / duration_ms / retrieval_results /
              route / route_guard / grading_mode / retrieved_count /
              citation_count / filters / top_k 的完整负载字典。
    """
    started_at = time.monotonic()
    resolved_filters = {}
    if session is not None:
        resolved_filters.update(normalize_context_filters(session.context_filters))
    resolved_filters.update(normalize_context_filters(filters))

    result = _RAG_GRAPH.invoke(
        {
            "question": question,
            "filters": filters or {},
            "top_k": top_k,
            "session": session,
            "provider": provider,
            "resolved_filters": resolved_filters,
        }
    )
    duration_ms = int((time.monotonic() - started_at) * 1000)
    return {
        "question": question,
        "query": result.get("rewritten_query") or question,
        "query_variants": result.get("query_variants")
        or _normalize_query_variants(
            result.get("rewritten_query") or question,
            limit=_chat_query_variant_limit(),
        ),
        "messages": result["messages"],
        "citations": result["citations"],
        "answer_mode": result["answer_mode"],
        "answer_notice": _build_answer_notice(result["answer_mode"]),
        "duration_ms": duration_ms,
        "retrieval_results": result["retrieval_results"],
        "route": result.get("route") or "direct",
        "route_guard": result.get("route_guard") or "default_direct",
        "grading_mode": "score_filter" if (result.get("route") or "direct") == "retrieve" else "none",
        "retrieved_count": len(result.get("retrieval_results") or []),
        "citation_count": len(result.get("citations") or []),
        "filters": resolved_filters,
        "top_k": top_k,
    }


def prepare_chat_payload_streaming(*, question, filters=None, top_k=5, session=None, provider=None):
    """
    准备发送给 LLM 的完整对话负载（流式模式）。

    使用 RAG 图的 stream 方法，产出过程事件和最终负载，便于前端展示进度。

    类比 SpringBoot：
      - 相当于返回 Flux 的 @Service 方法，逐步产出 RAG 流水线的中间状态。

    参数（均为关键字参数）：
      - question: str 用户问题（必填）。
      - filters: dict 上下文过滤条件（可选）。
      - top_k: int 检索返回条数，默认 5。
      - session: ChatSession|None 关联会话。
      - provider: object LLM 提供商实例。

    返回：
      - Generator[tuple[str, dict]]: (event_type, data) 二元组生成器。
        event_type 为 "step"（流水线进度）或 "payload"（最终负载）。
    """
    started_at = time.monotonic()
    resolved_filters = {}
    if session is not None:
        resolved_filters.update(normalize_context_filters(session.context_filters))
    resolved_filters.update(normalize_context_filters(filters))

    input_state = {
        "question": question,
        "filters": filters or {},
        "top_k": top_k,
        "session": session,
        "provider": provider,
        "resolved_filters": resolved_filters,
    }

    final_result = {}
    for mode, chunk in _RAG_GRAPH.stream(input_state, stream_mode=["updates", "custom"]):
        if mode == "custom":
            yield ("step", chunk)
        elif mode == "updates":
            for node_output in chunk.values():
                if node_output:
                    final_result.update(node_output)

    duration_ms = int((time.monotonic() - started_at) * 1000)
    payload = {
        "question": question,
        "query": final_result.get("rewritten_query") or question,
        "query_variants": final_result.get("query_variants")
        or _normalize_query_variants(
            final_result.get("rewritten_query") or question,
            limit=_chat_query_variant_limit(),
        ),
        "messages": final_result["messages"],
        "citations": final_result["citations"],
        "answer_mode": final_result["answer_mode"],
        "answer_notice": _build_answer_notice(final_result["answer_mode"]),
        "duration_ms": duration_ms,
        "retrieval_results": final_result.get("retrieval_results") or [],
        "route": final_result.get("route") or "direct",
        "route_guard": final_result.get("route_guard") or "default_direct",
        "grading_mode": "score_filter" if (final_result.get("route") or "direct") == "retrieve" else "none",
        "retrieved_count": len(final_result.get("retrieval_results") or []),
        "citation_count": len(final_result.get("citations") or []),
        "filters": resolved_filters,
        "top_k": top_k,
    }
    yield ("payload", payload)
