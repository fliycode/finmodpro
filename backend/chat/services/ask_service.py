"""
Chat 问答服务层（Ask Service）。

类比 SpringBoot：
  - ask_question() 和 stream_question() 相当于 @Service 类中的核心业务方法。
  - 负责编排 RAG + LLM 的完整问答流程：检索上下文 -> 构建提示词 -> 调用 LLM -> 后处理引用 -> 记录日志。
  - get_chat_provider() 相当于从 Spring IoC 容器获取 ChatProvider Bean。

流程概要：
  1. 获取 LLM 提供商实例
  2. 调用 RAG 图谱服务准备对话负载（prepare_chat_payload）
  3. 如果存在会话，记录用户消息并创建 assistant 占位消息
  4. 调用 LLM 生成回答
  5. 过滤回答中实际使用的引用
  6. 更新 assistant 消息为完成状态
  7. 触发异步的会话维护任务（标题生成、摘要更新、记忆提取）
  8. 记录检索日志用于后续分析和评估
"""

import logging
import re

from chat.services.rag_graph_service import prepare_chat_payload, prepare_chat_payload_streaming
from chat.services.session_service import (
    dispatch_session_maintenance_tasks,
    fail_session_message,
    finalize_session_message,
    start_session_turn,
)
from common.observability import trace_span
from llm.services.runtime_service import get_chat_provider
from rag.models import RetrievalLog
from rag.services.retrieval_log_service import create_retrieval_log

logger = logging.getLogger(__name__)

# 用于提取回答中引用编号的正则表达式。
# 匹配格式：[1], 【2】, 资料3, 引用4, 依据5
_CITATION_INDEX_PATTERN = re.compile(
    r"(?:\[|【)\s*(\d{1,2})\s*(?:\]|】)|(?:资料|引用|依据)\s*(\d{1,2})"
)


def _filter_citations_used_by_answer(citations, answer):
    """
    从引用列表中过滤出在答案中实际被使用到的引用。

    通过正则表达式提取 answer 文本中出现的引用编号（[1], 【2】, 资料3 等），
    只保留那些编号被实际引用的条目。

    参数：
      - citations: list[dict] 原始引用列表。
      - answer: str LLM 生成的回答文本。

    返回：
      - list[dict]: 仅包含实际被引用条目的过滤后列表。
        如果 answer 中没有任何引用编号，则返回全部原始引用。
    """
    citations = citations or []
    used_indexes = set()
    for match in _CITATION_INDEX_PATTERN.finditer(str(answer or "")):
        raw_index = match.group(1) or match.group(2)
        try:
            used_indexes.add(int(raw_index))
        except (TypeError, ValueError):
            continue

    if not used_indexes:
        return citations

    return [
        citation
        for index, citation in enumerate(citations, start=1)
        if index in used_indexes
    ]


def _record_retrieval_log(payload):
    """
    将 RAG 检索过程的关键信息记录到检索日志。

    参数：
      - payload: dict，来自 prepare_chat_payload 的完整负载，
                 包含 question / top_k / filters / retrieval_results / duration_ms 等字段。

    无返回值，调用 create_retrieval_log 写入数据库。
    检索日志用于后续的评估分析、性能调优和行为审计。
    """
    create_retrieval_log(
        query=payload["question"],
        top_k=payload["top_k"],
        filters=payload["filters"],
        results=payload["retrieval_results"],
        source=RetrievalLog.SOURCE_CHAT_ASK,
        duration_ms=payload["duration_ms"],
        metadata={
            "route": payload.get("route"),
            "route_guard": payload.get("route_guard"),
            "rewritten_query": payload.get("query"),
            "query_variants": payload.get("query_variants") or [],
            "grading_mode": payload.get("grading_mode"),
            "retrieved_count": payload.get("retrieved_count"),
            "citation_count": payload.get("citation_count"),
            "answer_mode": payload.get("answer_mode"),
        },
    )


def _dispatch_session_maintenance_tasks_non_blocking(*, session_id):
    """
    以非阻塞方式派发会话维护任务（Celery 异步任务）。

    即使派发失败也不会影响主流程的问答响应，仅记录异常日志。

    参数：
      - session_id: int 会话 ID。
    """
    try:
        dispatch_session_maintenance_tasks(session_id=session_id)
    except Exception:
        logger.exception("chat session maintenance dispatch failed", extra={"session_id": session_id})


def ask_question(*, question, filters=None, top_k=5, session=None):
    """
    同步问答：给定用户问题，返回 LLM 生成的完整回答。

    类比 SpringBoot：
      - 相当于 @Service 方法，由 Controller 调用，协调多个下游服务完成业务逻辑。

    参数（均为关键字参数）：
      - question: str 用户提问的原始文本（必填）。
      - filters: dict 上下文过滤条件（可选），如 {"dataset_id": 1}。
      - top_k: int 检索返回条数上限，默认 5。
      - session: ChatSession | None 关联的会话对象（可选），非 None 时将该轮对话写入会话。

    返回：
      - dict: {
            "question": str,           # 原始问题
            "query": str,              # 重写后的检索查询
            "answer": str,             # LLM 生成的回答
            "citations": list[dict],   # 过滤后的引用列表
            "answer_mode": str,        # 回答模式（cited / fallback / direct）
            "answer_notice": str|None, # 回落提示信息
            "duration_ms": int,        # 处理耗时（毫秒）
        }

    异常：
      - ServiceConfigurationError: 模型/提供商配置错误 -> 503
      - UpstreamServiceError: 上游 LLM 服务异常 -> 相应错误码
      - ValueError: 参数不合法 -> 400
    """
    provider = get_chat_provider()
    with trace_span(
        "chat.ask",
        metadata={"top_k": top_k, "session_id": getattr(session, "id", None)},
        input_data={"question": question},
    ) as observation:
        payload = prepare_chat_payload(
            question=question,
            filters=filters,
            top_k=top_k,
            session=session,
            provider=provider,
        )
        assistant_message = None
        if session is not None:
            _, assistant_message = start_session_turn(
                session=session,
                question=payload["question"],
            )

        try:
            answer = provider.chat(messages=payload["messages"]).content
        except Exception:
            if assistant_message is not None:
                fail_session_message(
                    message=assistant_message,
                    model_metadata={"answer_mode": payload["answer_mode"]},
                )
            raise

        final_citations = _filter_citations_used_by_answer(payload["citations"], answer)
        if assistant_message is not None:
            finalize_session_message(
                message=assistant_message,
                content=answer,
                citations=final_citations,
                model_metadata={"answer_mode": payload["answer_mode"]},
            )
            _dispatch_session_maintenance_tasks_non_blocking(session_id=session.id)

        _record_retrieval_log(payload)
        observation.update(
            output={
                "answer_mode": payload["answer_mode"],
                "citation_count": len(final_citations),
                "duration_ms": payload["duration_ms"],
            }
        )
        return {
            "question": payload["question"],
            "query": payload["query"],
            "answer": answer,
            "citations": final_citations,
            "answer_mode": payload["answer_mode"],
            "answer_notice": payload["answer_notice"],
            "duration_ms": payload["duration_ms"],
        }


def stream_question(*, question, filters=None, top_k=5, session=None):
    """
    流式问答：返回一个事件生成器，逐步输出 RAG 步骤和 LLM 生成的文本块。

    类比 SpringBoot：
      - 相当于返回 Flux<Event> 的 @Service 方法，支持 SSE 流式传输。

    参数（均为关键字参数）：
      - question: str 用户提问的原始文本（必填）。
      - filters: dict 上下文过滤条件（可选）。
      - top_k: int 检索返回条数上限，默认 5。
      - session: ChatSession | None 关联的会话对象（可选）。

    返回：
      - Generator[dict]: 事件生成器，每个事件格式为 {"event": str, "data": dict}。
        事件类型：
          - "step": RAG 流水线步骤（route / rewrite_query / retrieve / score_filter / build_context）
          - "meta": 元数据信息（question / answer_mode / citation_count / answer_notice / duration_ms）
          - "chunk": LLM 输出文本块 {"content": "...文字片段..."}
          - "done": 回答完成（含完整 answer / citations）
          - "error": 错误事件
    """
    provider = get_chat_provider()

    def event_stream():
        """
        内部生成器：先通过 RAG 图谱获取负载，再流式调用 LLM 并逐步 yield 事件。

        RAG 图谱流式输出中会穿插 'step' 事件和最终的 'payload' 数据。
        """
        payload = None
        for event_type, data in prepare_chat_payload_streaming(
            question=question,
            filters=filters,
            top_k=top_k,
            session=session,
            provider=provider,
        ):
            if event_type == "step":
                yield {"event": "step", "data": data}
            elif event_type == "payload":
                payload = data

        if payload is None:
            yield {"event": "error", "data": {"message": "RAG pipeline produced no output"}}
            return

        assistant_message = None
        with trace_span(
            "chat.ask.stream",
            metadata={"top_k": top_k, "session_id": getattr(session, "id", None)},
            input_data={"question": question},
        ) as observation:
            if session is not None:
                _, assistant_message = start_session_turn(
                    session=session,
                    question=payload["question"],
                )

            yield {
                "event": "meta",
                "data": {
                    "question": payload["question"],
                    "query": payload["query"],
                    "citations": [],
                    "citation_count": len(payload["citations"]),
                    "answer_mode": payload["answer_mode"],
                    "answer_notice": payload["answer_notice"],
                    "duration_ms": payload["duration_ms"],
                },
            }

            chunks = []
            stream_method = getattr(provider, "stream", None)
            try:
                if callable(stream_method):
                    # provider 支持流式输出，逐个 yield chunk
                    for chunk in stream_method(messages=payload["messages"]):
                        text = str(chunk or "")
                        if not text:
                            continue
                        chunks.append(text)
                        yield {"event": "chunk", "data": {"content": text}}
                else:
                    # provider 不支持流式，一次性获取完整回答后作为一个 chunk 输出
                    answer = provider.chat(messages=payload["messages"]).content
                    chunks.append(answer)
                    yield {"event": "chunk", "data": {"content": answer}}
            except Exception:
                if assistant_message is not None:
                    fail_session_message(
                        message=assistant_message,
                        content="".join(chunks),
                        model_metadata={"answer_mode": payload["answer_mode"]},
                    )
                raise

            answer = "".join(chunks)
            final_citations = _filter_citations_used_by_answer(payload["citations"], answer)
            if assistant_message is not None:
                finalize_session_message(
                    message=assistant_message,
                    content=answer,
                    citations=final_citations,
                    model_metadata={"answer_mode": payload["answer_mode"]},
                )
                _dispatch_session_maintenance_tasks_non_blocking(session_id=session.id)

            _record_retrieval_log(payload)
            observation.update(
                output={
                    "answer_mode": payload["answer_mode"],
                    "citation_count": len(final_citations),
                    "duration_ms": payload["duration_ms"],
                    "stream_chunk_count": len(chunks),
                }
            )
            yield {
                "event": "done",
                "data": {
                    "answer": answer,
                    "citations": final_citations,
                    "answer_mode": payload["answer_mode"],
                    "answer_notice": payload["answer_notice"],
                    "duration_ms": payload["duration_ms"],
                },
            }

    return event_stream()
