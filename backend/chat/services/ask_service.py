import logging
import time

from chat.services.context_service import build_chat_messages
from chat.services.session_service import (
    dispatch_session_maintenance_tasks,
    fail_session_message,
    finalize_session_message,
    normalize_context_filters,
    start_session_turn,
)
from common.observability import trace_span
from llm.services.runtime_service import get_chat_provider
from rag.models import RetrievalLog
from rag.services.retrieval_log_service import create_retrieval_log
from rag.services.retrieval_service import build_retrieval_response, retrieve

logger = logging.getLogger(__name__)


def _build_answer_notice(citations):
    if citations:
        return None
    return "当前回答未命中知识库引用，仅基于通用模型能力生成，请注意甄别。"


def _resolve_filters(filters=None, session=None):
    resolved_filters = {}
    if session is not None:
        resolved_filters.update(normalize_context_filters(session.context_filters))
    resolved_filters.update(normalize_context_filters(filters))
    return resolved_filters


def _prepare_answer(question, filters=None, top_k=5, session=None):
    started_at = time.monotonic()
    resolved_filters = _resolve_filters(filters, session=session)
    retrieval_results = retrieve(query=question, filters=resolved_filters, top_k=top_k)
    retrieval_payload = build_retrieval_response(query=question, results=retrieval_results)
    citations = retrieval_payload["citations"]
    duration_ms = int((time.monotonic() - started_at) * 1000)
    return {
        "question": question,
        "query": question,
        "messages": build_chat_messages(
            session=session,
            question=question,
            citations=citations,
            filters=resolved_filters,
        ),
        "citations": citations,
        "answer_mode": "cited" if citations else "fallback",
        "answer_notice": _build_answer_notice(citations),
        "duration_ms": duration_ms,
        "retrieval_results": retrieval_results,
        "filters": resolved_filters,
        "top_k": top_k,
    }


def _record_retrieval_log(payload):
    create_retrieval_log(
        query=payload["question"],
        top_k=payload["top_k"],
        filters=payload["filters"],
        results=payload["retrieval_results"],
        source=RetrievalLog.SOURCE_CHAT_ASK,
        duration_ms=payload["duration_ms"],
    )


def _dispatch_session_maintenance_tasks_non_blocking(*, session_id):
    try:
        dispatch_session_maintenance_tasks(session_id=session_id)
    except Exception:
        logger.exception("chat session maintenance dispatch failed", extra={"session_id": session_id})


def ask_question(*, question, filters=None, top_k=5, session=None):
    with trace_span(
        "chat.ask",
        metadata={"top_k": top_k, "session_id": getattr(session, "id", None)},
        input_data={"question": question},
    ) as observation:
        payload = _prepare_answer(question, filters=filters, top_k=top_k, session=session)
        assistant_message = None
        if session is not None:
            _, assistant_message = start_session_turn(
                session=session,
                question=payload["question"],
            )

        try:
            answer = get_chat_provider().chat(messages=payload["messages"])
        except Exception:
            if assistant_message is not None:
                fail_session_message(
                    message=assistant_message,
                    model_metadata={"answer_mode": payload["answer_mode"]},
                )
            raise

        if assistant_message is not None:
            finalize_session_message(
                message=assistant_message,
                content=answer,
                citations=payload["citations"],
                model_metadata={"answer_mode": payload["answer_mode"]},
            )
            _dispatch_session_maintenance_tasks_non_blocking(session_id=session.id)

        _record_retrieval_log(payload)
        observation.update(
            output={
                "answer_mode": payload["answer_mode"],
                "citation_count": len(payload["citations"]),
                "duration_ms": payload["duration_ms"],
            }
        )
        return {
            "question": payload["question"],
            "query": payload["query"],
            "answer": answer,
            "citations": payload["citations"],
            "answer_mode": payload["answer_mode"],
            "answer_notice": payload["answer_notice"],
            "duration_ms": payload["duration_ms"],
        }


def stream_question(*, question, filters=None, top_k=5, session=None):
    payload = _prepare_answer(question, filters=filters, top_k=top_k, session=session)
    provider = get_chat_provider()

    def event_stream():
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
                    "citations": payload["citations"],
                    "answer_mode": payload["answer_mode"],
                    "answer_notice": payload["answer_notice"],
                    "duration_ms": payload["duration_ms"],
                },
            }

            chunks = []
            stream_method = getattr(provider, "stream", None)
            try:
                if callable(stream_method):
                    for chunk in stream_method(messages=payload["messages"]):
                        text = str(chunk or "")
                        if not text:
                            continue
                        chunks.append(text)
                        yield {"event": "chunk", "data": {"content": text}}
                else:
                    answer = provider.chat(messages=payload["messages"])
                    chunks.append(answer)
                    yield {"event": "chunk", "data": {"content": answer}}
            except Exception:
                if assistant_message is not None:
                    fail_session_message(
                        message=assistant_message,
                        model_metadata={"answer_mode": payload["answer_mode"]},
                    )
                raise

            answer = "".join(chunks)
            if assistant_message is not None:
                finalize_session_message(
                    message=assistant_message,
                    content=answer,
                    citations=payload["citations"],
                    model_metadata={"answer_mode": payload["answer_mode"]},
                )
                _dispatch_session_maintenance_tasks_non_blocking(session_id=session.id)

            _record_retrieval_log(payload)
            observation.update(
                output={
                    "answer_mode": payload["answer_mode"],
                    "citation_count": len(payload["citations"]),
                    "duration_ms": payload["duration_ms"],
                    "stream_chunk_count": len(chunks),
                }
            )
            yield {
                "event": "done",
                "data": {
                    "answer": answer,
                    "citations": payload["citations"],
                    "answer_mode": payload["answer_mode"],
                    "answer_notice": payload["answer_notice"],
                    "duration_ms": payload["duration_ms"],
                },
            }

    return event_stream()
