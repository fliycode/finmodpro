import json
import logging
import re
import time
from typing import TypedDict

from django.conf import settings
from langgraph.config import get_stream_writer
from langgraph.graph import END, START, StateGraph

from chat.services.context_service import build_chat_messages
from chat.services.session_service import normalize_context_filters
from chat.services.store import django_memory_store
from rag.services.retrieval_backend_service import retrieve_chat_context
from rag.services.rerank_service import rerank_with_variants
from rag.services.retrieval_service import build_retrieval_response

logger = logging.getLogger(__name__)

MAX_CHAT_CITATIONS = 3


def retrieve_chat_context_results(*, query, filters=None, top_k=None, query_variants=None):
    return retrieve_chat_context(
        query=query,
        filters=filters,
        top_k=top_k or 5,
        query_variants=query_variants,
    )

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
_DOCUMENT_SOURCE_PATTERNS = (
    "知识库",
    "上传",
    "文档",
    "文件",
    "资料",
    "材料",
    "报告",
    "报表",
    "财报",
    "年报",
    "审计报告",
    "开题报告",
    "论文",
    "合同",
    "制度",
    "方案",
    "计划书",
    "手册",
    "纪要",
    "公告",
    "通知",
    "document",
    "file",
    "report",
    "memo",
)
_DOCUMENT_LOOKUP_PATTERNS = (
    "查",
    "查询",
    "找",
    "检索",
    "看一下",
    "告诉我",
    "是什么",
    "有哪些",
    "多少",
    "题目",
    "标题",
    "名称",
    "内容",
    "摘要",
    "结论",
    "作者",
    "日期",
    "时间",
    "title",
    "what is",
    "which",
    "find",
    "search",
)
_GENERATION_PATTERNS = (
    "生成",
    "写",
    "撰写",
    "起草",
    "拟定",
    "设计",
    "建议",
    "推荐",
)
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

_JSON_OBJECT_PATTERN = re.compile(r"\{.*\}", re.DOTALL)
_FENCED_JSON_PATTERN = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL | re.IGNORECASE)


class ChatRagState(TypedDict, total=False):
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
    if answer_mode != "fallback":
        return None
    return "当前回答未命中知识库引用，仅基于通用模型能力生成，请注意甄别。"


def _normalize_question_text(question):
    return " ".join(str(question or "").strip().lower().split())


def _has_direct_assistant_intent(question):
    normalized = _normalize_question_text(question)
    return any(pattern in normalized for pattern in _DIRECT_ASSISTANT_PATTERNS)


def _has_document_lookup_intent(question):
    normalized = _normalize_question_text(question)
    if not normalized:
        return False
    has_source_hint = any(pattern in normalized for pattern in _DOCUMENT_SOURCE_PATTERNS)
    has_lookup_hint = any(pattern in normalized for pattern in _DOCUMENT_LOOKUP_PATTERNS)
    asks_to_create = any(pattern in normalized for pattern in _GENERATION_PATTERNS)
    if asks_to_create and not any(pattern in normalized for pattern in ("根据", "基于", "参考", "知识库", "上传")):
        return False
    return has_source_hint and has_lookup_hint


def _has_constrained_response_intent(question):
    normalized = _normalize_question_text(question)
    if not normalized:
        return False
    return any(pattern in normalized for pattern in _CONSTRAINED_RESPONSE_PATTERNS)


def _parse_json_candidate(raw_text):
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
    if not isinstance(parsed, dict):
        return _normalize_query_variants(fallback_query, limit=limit)
    raw_variants = parsed.get("query_variants") or parsed.get("queries") or parsed.get("variants") or []
    return _normalize_query_variants(
        parsed.get("rewritten_query") or fallback_query,
        raw_variants,
        limit=limit,
    )


def _chat_query_variant_limit():
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
    try:
        return float(item.get(key))
    except (TypeError, ValueError):
        return None


def _best_relevance_score(item):
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
    return float(getattr(settings, "RAG_SCORE_FILTER_THRESHOLD", 0.12))


def _select_relevant_results(results, *, limit=MAX_CHAT_CITATIONS):
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


# --- Graph nodes ---


def _emit_step(data: dict):
    """Safely push a step event via LangGraph stream writer."""
    try:
        get_stream_writer()(data)
    except Exception:
        pass


def _route_by_rules(state: ChatRagState):
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
    elif _has_document_lookup_intent(question):
        route = "retrieve"
        route_guard = "document_lookup_intent"
    else:
        route = "direct"
        route_guard = "default_direct"
    logger.info(
        "chat rag route",
        extra={"question": question, "route": route, "route_guard": route_guard},
    )
    _emit_step({"step": "route", "route": route, "route_guard": route_guard})
    return {"route": route, "route_guard": route_guard}


def _rewrite_query(state: ChatRagState):
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
    rewritten_query = state.get("rewritten_query") or state["question"]
    query_variants = state.get("query_variants") or _normalize_query_variants(
        rewritten_query,
        limit=_chat_query_variant_limit(),
    )
    requested_top_k = int(state["top_k"])
    retrieval_top_k = requested_top_k
    candidate_limit = MAX_CHAT_CITATIONS
    if _has_document_lookup_intent(state["question"]):
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
    return "rewrite_query" if state.get("route") == "retrieve" else "direct_answer_context"


def _build_rag_graph():
    graph = StateGraph(ChatRagState)
    graph.add_node("route", _route_by_rules)
    graph.add_node("rewrite_query", _rewrite_query)
    graph.add_node("retrieve_and_merge", _retrieve_and_merge)
    graph.add_node("score_filter", _score_filter)
    graph.add_node("build_retrieval_context", _build_retrieval_context)
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
    graph.add_edge("score_filter", "build_retrieval_context")
    graph.add_edge("build_retrieval_context", END)
    graph.add_edge("direct_answer_context", END)
    return graph.compile(store=django_memory_store)


_RAG_GRAPH = _build_rag_graph()


def prepare_chat_payload(*, question, filters=None, top_k=5, session=None, provider=None, retrieve_fn=None):
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
    """Yield (event_type, data) tuples. event_type is 'step' or 'payload'.

    'step' events carry RAG pipeline progress from get_stream_writer().
    'payload' is the final prepared payload for LLM streaming.
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
