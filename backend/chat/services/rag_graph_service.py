import json
import logging
import re
import time
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from chat.services.context_service import build_chat_messages
from chat.services.session_service import normalize_context_filters
from rag.services.retrieval_service import build_retrieval_response, retrieve as default_retrieve

logger = logging.getLogger(__name__)

MAX_CHAT_CITATIONS = 3
MIN_CHAT_CITATION_SCORE = 0.12

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

_ROUTER_JSON_PATTERN = re.compile(r"\{.*\}", re.DOTALL)
_JSON_OBJECT_PATTERN = re.compile(r"\{.*\}", re.DOTALL)
_FENCED_JSON_PATTERN = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL | re.IGNORECASE)


class ChatRagState(TypedDict, total=False):
    question: str
    filters: dict
    top_k: int
    session: object
    provider: object
    retrieve_fn: object
    resolved_filters: dict
    route: str
    route_guard: str
    rewritten_query: str
    retrieval_results: list
    graded_results: list
    grading_mode: str
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


def _guard_route_decision(decision, question):
    if _has_direct_assistant_intent(question):
        return {
            "route": "direct",
            "rewritten_query": question,
            "route_guard": "direct_assistant_intent",
        }
    if _has_document_lookup_intent(question):
        return {
            **decision,
            "route": "retrieve",
            "route_guard": "document_lookup_intent",
        }
    return {**decision, "route_guard": "none"}


def _fallback_route(question):
    if not _normalize_question_text(question):
        return {"route": "direct", "rewritten_query": question}
    if _has_direct_assistant_intent(question):
        return {"route": "direct", "rewritten_query": question}
    return {"route": "retrieve", "rewritten_query": question}


def _parse_router_output(raw_text, question):
    text = str(raw_text or "").strip()
    match = _ROUTER_JSON_PATTERN.search(text)
    candidate = match.group(0) if match else text
    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError:
        return _fallback_route(question)

    route = str(parsed.get("route") or "").strip().lower()
    rewritten_query = str(parsed.get("rewritten_query") or question).strip() or question
    if route not in {"direct", "retrieve"}:
        return _fallback_route(question)
    return {"route": route, "rewritten_query": rewritten_query}


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


def _extract_relevant_indexes(parsed):
    if isinstance(parsed, list):
        return parsed
    if not isinstance(parsed, dict):
        return None
    for key in (
        "relevant_indexes",
        "relevantIndexes",
        "indexes",
        "indices",
        "selected_indexes",
        "selectedIndexes",
        "selected",
    ):
        if key in parsed:
            value = parsed.get(key)
            if isinstance(value, list):
                return value
            if value in (None, ""):
                return []
            return [value]
    return None


def _coerce_relevant_index(value):
    if isinstance(value, dict):
        value = value.get("index") or value.get("idx") or value.get("id")
    return int(str(value).strip())


def _route_question(state: ChatRagState):
    question = state["question"]
    provider = state["provider"]
    prompt = [
        {
            "role": "system",
            "content": (
                "你是 FinModPro 聊天问答系统的检索路由器。"
                "判断当前问题应该直接由模型回答，还是先检索金融知识库后再回答。"
                "当问题需要引用企业文档、用户上传资料、报告、论文、制度、财务资料、风险事件、知识库事实或数据证据时选择 retrieve。"
                "用户问某份报告/文档/资料的题目、标题、内容、摘要、结论、日期、作者或具体数值时必须选择 retrieve。"
                "如果问题是在问平台身份、你是谁、平台是什么、你能做什么、寒暄问候、纯闲聊，则选择 direct。"
                "输出严格 JSON：{\"route\":\"direct|retrieve\",\"rewritten_query\":\"...\"}，不要输出额外文本。"
            ),
        },
        {"role": "user", "content": question},
    ]
    try:
        raw_output = provider.chat(messages=prompt, options={"temperature": 0, "max_tokens": 64})
    except Exception:
        logger.exception("chat rag router failed; falling back to heuristic route")
        decision = _fallback_route(question)
    else:
        decision = _parse_router_output(raw_output, question)
    decision = _guard_route_decision(decision, question)
    logger.info(
        "chat rag router decision",
        extra={
            "question": question,
            "route": decision["route"],
            "rewritten_query": decision["rewritten_query"],
            "route_guard": decision["route_guard"],
        },
    )
    return decision


def _rewrite_query(state: ChatRagState):
    question = state["question"]
    provider = state["provider"]
    prompt = [
        {
            "role": "system",
            "content": (
                "你是 FinModPro 的检索查询重写器。"
                "请把用户问题改写成更适合检索金融知识库的查询，保留关键实体、财务指标、时间范围和文档线索。"
                "输出严格 JSON：{\"rewritten_query\":\"...\"}，不要输出额外文本。"
            ),
        },
        {"role": "user", "content": question},
    ]
    try:
        raw_output = provider.chat(messages=prompt, options={"temperature": 0, "max_tokens": 64})
    except Exception:
        logger.exception("chat rag rewrite provider failed; falling back to original question")
        rewritten_query = state.get("rewritten_query") or question
    else:
        try:
            parsed = _parse_json_candidate(raw_output)
            if not isinstance(parsed, dict):
                raise ValueError("rewrite response is not a JSON object")
            rewritten_query = str(parsed.get("rewritten_query") or "").strip() or question
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            logger.warning(
                "chat rag rewrite returned invalid JSON; falling back to original question",
                extra={"error": str(exc)},
            )
            rewritten_query = state.get("rewritten_query") or question
    logger.info(
        "chat rag rewrite",
        extra={
            "question": question,
            "rewritten_query": rewritten_query,
        },
    )
    return {"rewritten_query": rewritten_query}


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


def _select_relevant_results(results, *, limit=MAX_CHAT_CITATIONS):
    relevant = []
    for item in results:
        score = _best_relevance_score(item)
        if score is not None and score < MIN_CHAT_CITATION_SCORE:
            continue
        relevant.append(item)
    if limit is None:
        return relevant
    return relevant[:limit]


def _retrieve_context(state: ChatRagState):
    rewritten_query = state.get("rewritten_query") or state["question"]
    requested_top_k = int(state["top_k"])
    retrieval_top_k = requested_top_k
    candidate_limit = MAX_CHAT_CITATIONS
    if state.get("route_guard") == "document_lookup_intent":
        retrieval_top_k = max(requested_top_k * 4, 20)
        candidate_limit = retrieval_top_k
    retrieval_results = _select_relevant_results(
        state["retrieve_fn"](
            query=rewritten_query,
            filters=state["resolved_filters"],
            top_k=retrieval_top_k,
        ),
        limit=candidate_limit,
    )
    logger.info(
        "chat rag retrieve",
        extra={
            "question": state["question"],
            "rewritten_query": rewritten_query,
            "top_k": retrieval_top_k,
            "retrieved_count": len(retrieval_results),
        },
    )
    return {"retrieval_results": retrieval_results}


def _fallback_grade_results(results):
    return _select_relevant_results(results)


def _grade_retrieval(state: ChatRagState):
    results = state.get("retrieval_results") or []
    if not results:
        logger.info(
            "chat rag grade",
            extra={
                "question": state["question"],
                "graded_count": 0,
                "grading_mode": "empty",
            },
        )
        return {"graded_results": [], "grading_mode": "empty"}

    provider = state["provider"]
    serialized_results = [
        {
            "index": index,
            "document_title": item.get("document_title"),
            "snippet": item.get("snippet"),
            "score": item.get("score"),
            "rerank_score": item.get("rerank_score"),
        }
        for index, item in enumerate(results, start=1)
    ]
    prompt = [
        {
            "role": "system",
            "content": (
                "你是 FinModPro 的检索相关性评估器。"
                "从候选资料里挑选真正与问题直接相关、值得提供给回答模型的条目。"
                "最多保留 3 条。没有直接相关资料时输出空数组。"
                "输出严格 JSON：{\"relevant_indexes\":[1,2,...]}。"
            ),
        },
        {
            "role": "user",
            "content": json.dumps(
                {
                    "question": state["question"],
                    "candidates": serialized_results,
                },
                ensure_ascii=False,
            ),
        },
    ]
    try:
        raw_output = provider.chat(messages=prompt, options={"temperature": 0, "max_tokens": 64})
    except Exception:
        logger.exception("chat rag grading provider failed; falling back to score-based grading")
        graded_results = _fallback_grade_results(results)
        grading_mode = "fallback"
    else:
        try:
            parsed = _parse_json_candidate(raw_output)
            raw_indexes = _extract_relevant_indexes(parsed)
            if raw_indexes is None:
                raise ValueError("grade response missing relevant_indexes")
            normalized_indexes = set()
            for value in raw_indexes:
                normalized_indexes.add(_coerce_relevant_index(value))
            selected = [
                item
                for index, item in enumerate(results, start=1)
                if index in normalized_indexes
            ]
            graded_results = _select_relevant_results(selected)
            grading_mode = "llm"
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            logger.warning(
                "chat rag grading returned invalid JSON; falling back to score-based grading",
                extra={"error": str(exc)},
            )
            graded_results = _fallback_grade_results(results)
            grading_mode = "fallback"
    logger.info(
        "chat rag grade",
        extra={
            "question": state["question"],
            "graded_count": len(graded_results),
            "grading_mode": grading_mode,
        },
    )
    return {"graded_results": graded_results, "grading_mode": grading_mode}


def _build_retrieval_context(state: ChatRagState):
    graded_results = state.get("graded_results") or []
    citations = build_retrieval_response(
        query=state["question"],
        results=graded_results,
    )["citations"]
    answer_mode = "cited" if citations else "fallback"
    return {
        "retrieval_results": graded_results,
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
            session=None,
            question=state["question"],
            citations=[],
            filters={},
        ),
    }


def _route_after_router(state: ChatRagState):
    return "rewrite_query" if state.get("route") == "retrieve" else "direct_answer_context"


def _build_rag_graph():
    graph = StateGraph(ChatRagState)
    graph.add_node("route_question", _route_question)
    graph.add_node("rewrite_query", _rewrite_query)
    graph.add_node("retrieve_context", _retrieve_context)
    graph.add_node("grade_retrieval", _grade_retrieval)
    graph.add_node("build_retrieval_context", _build_retrieval_context)
    graph.add_node("direct_answer_context", _direct_answer_context)
    graph.add_edge(START, "route_question")
    graph.add_conditional_edges(
        "route_question",
        _route_after_router,
        {
            "rewrite_query": "rewrite_query",
            "direct_answer_context": "direct_answer_context",
        },
    )
    graph.add_edge("rewrite_query", "retrieve_context")
    graph.add_edge("retrieve_context", "grade_retrieval")
    graph.add_edge("grade_retrieval", "build_retrieval_context")
    graph.add_edge("build_retrieval_context", END)
    graph.add_edge("direct_answer_context", END)
    return graph.compile()


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
            "retrieve_fn": retrieve_fn or default_retrieve,
            "resolved_filters": resolved_filters,
        }
    )
    duration_ms = int((time.monotonic() - started_at) * 1000)
    return {
        "question": question,
        "query": result.get("rewritten_query") or question,
        "messages": result["messages"],
        "citations": result["citations"],
        "answer_mode": result["answer_mode"],
        "answer_notice": _build_answer_notice(result["answer_mode"]),
        "duration_ms": duration_ms,
        "retrieval_results": result["retrieval_results"],
        "route": result.get("route") or "direct",
        "route_guard": result.get("route_guard") or "none",
        "grading_mode": result.get("grading_mode") or "none",
        "retrieved_count": len(result.get("retrieval_results") or []),
        "citation_count": len(result.get("citations") or []),
        "filters": resolved_filters,
        "top_k": top_k,
    }
