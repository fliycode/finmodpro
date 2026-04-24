import logging
import re

from chat.services.rag_graph_service import prepare_chat_payload
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
from rag.services.retrieval_service import retrieve

logger = logging.getLogger(__name__)

_CITATION_INDEX_PATTERN = re.compile(
    r"(?:\[|【)\s*(\d{1,2})\s*(?:\]|】)|(?:资料|引用|依据)\s*(\d{1,2})"
)


def _filter_citations_used_by_answer(citations, answer):
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
            retrieve_fn=retrieve,
        )
        assistant_message = None
        if session is not None:
            _, assistant_message = start_session_turn(
                session=session,
                question=payload["question"],
            )

        try:
            answer = provider.chat(messages=payload["messages"])
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
    provider = get_chat_provider()
    payload = prepare_chat_payload(
        question=question,
        filters=filters,
        top_k=top_k,
        session=session,
        provider=provider,
        retrieve_fn=retrieve,
    )

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
