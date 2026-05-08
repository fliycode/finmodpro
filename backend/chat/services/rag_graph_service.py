import json
import logging
import re
import time
from typing import TypedDict

from django.conf import settings
from langgraph.graph import END, START, StateGraph

from chat.services.context_service import build_chat_messages
from chat.services.session_service import normalize_context_filters
from chat.services.store import django_memory_store
from rag.services.lightrag_retrieval_service import retrieve_from_lightrag
from rag.services.rerank_service import rerank_with_variants
from rag.services.retrieval_service import build_retrieval_response

logger = logging.getLogger(__name__)

MAX_CHAT_CITATIONS = 3

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


def _normalize_query_variants(*queries):
    limit = max(int(getattr(settings, "RAG_MULTI_QUERY_VARIANT_COUNT", 1) or 1), 1)
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
    return normalized[:limit]


def _extract_query_variants(parsed, fallback_query):
    if not isinstance(parsed, dict):
        return _normalize_query_variants(fallback_query)
    raw_variants = parsed.get("query_variants") or parsed.get("queries") or parsed.get("variants") or []
    return _normalize_query_variants(parsed.get("rewritten_query") or fallback_query, raw_variants)


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


def _route_by_rules(state: ChatRagState):
    question = state["question"]
    if _has_direct_assistant_intent(question):
        route = "direct"
    elif _has_document_lookup_intent(question):
        route = "retrieve"
    else:
        route = "retrieve"
    logger.info(
        "chat rag route",
        extra={"question": question, "route": route},
    )
    return {"route": route}


def _rewrite_query(state: ChatRagState):
    question = state["question"]
    provider = state["provider"]
    max_query_variants = max(int(getattr(settings, "RAG_MULTI_QUERY_VARIANT_COUNT", 1) or 1), 1)
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
        raw_output = provider.chat(messages=prompt, options={"temperature": 0, "max_tokens": 64})
    except Exception:
        logger.exception("chat rag rewrite provider failed; falling back to original question")
        rewritten_query = question
        query_variants = _normalize_query_variants(question)
    else:
        try:
            parsed = _parse_json_candidate(raw_output)
            if not isinstance(parsed, dict):
                raise ValueError("rewrite response is not a JSON object")
            rewritten_query = str(parsed.get("rewritten_query") or "").strip() or question
            query_variants = _extract_query_variants(parsed, rewritten_query)
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            logger.warning(
                "chat rag rewrite returned invalid JSON; falling back to original question",
                extra={"error": str(exc)},
            )
            rewritten_query = question
            query_variants = _normalize_query_variants(question)
    logger.info(
        "chat rag rewrite",
        extra={
            "question": question,
            "rewritten_query": rewritten_query,
            "query_variants": query_variants,
        },
    )
    return {
        "rewritten_query": rewritten_query,
        "query_variants": query_variants,
    }


def _retrieve_and_merge(state: ChatRagState):
    rewritten_query = state.get("rewritten_query") or state["question"]
    query_variants = state.get("query_variants") or _normalize_query_variants(rewritten_query)
    requested_top_k = int(state["top_k"])
    retrieval_top_k = requested_top_k
    candidate_limit = MAX_CHAT_CITATIONS
    if _has_document_lookup_intent(state["question"]):
        retrieval_top_k = max(requested_top_k * 4, 20)
        candidate_limit = retrieval_top_k

    raw_results = retrieve_from_lightrag(
        query=rewritten_query,
        top_k=retrieval_top_k,
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
            "retrieval_source": "lightrag" if raw_results else "none",
        },
    )
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
    return {"retrieval_results": filtered}


def _build_retrieval_context(state: ChatRagState):
    retrieval_results = state.get("retrieval_results") or []
    citations = build_retrieval_response(
        query=state["question"],
        results=retrieval_results,
    )["citations"]
    answer_mode = "cited" if citations else "fallback"
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
        or _normalize_query_variants(result.get("rewritten_query") or question),
        "messages": result["messages"],
        "citations": result["citations"],
        "answer_mode": result["answer_mode"],
        "answer_notice": _build_answer_notice(result["answer_mode"]),
        "duration_ms": duration_ms,
        "retrieval_results": result["retrieval_results"],
        "route": result.get("route") or "direct",
        "route_guard": "none",
        "grading_mode": "score_filter",
        "retrieved_count": len(result.get("retrieval_results") or []),
        "citation_count": len(result.get("citations") or []),
        "filters": resolved_filters,
        "top_k": top_k,
    }
