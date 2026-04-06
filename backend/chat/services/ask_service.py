import time

from llm.services.prompt_service import render_prompt
from llm.services.runtime_service import get_chat_provider
from rag.models import RetrievalLog
from rag.services.retrieval_log_service import create_retrieval_log
from rag.services.retrieval_service import build_retrieval_response, retrieve


def _build_context(citations):
    if not citations:
        return "当前没有可用的参考资料。"

    lines = []
    for index, citation in enumerate(citations, start=1):
        lines.append(
            f"[{index}] {citation['document_title']} {citation['page_label']}: {citation['snippet']}"
        )
    return "\n".join(lines)


def _build_answer_notice(citations):
    if citations:
        return None
    return "当前回答未命中知识库引用，仅基于通用模型能力生成，请注意甄别。"


def _build_messages(question, citations):
    if not citations:
        return [{"role": "user", "content": question}]

    prompt = render_prompt(
        "chat/answer.txt",
        question=question,
        context=_build_context(citations),
    )
    return [{"role": "user", "content": prompt}]


def _prepare_answer(question, filters=None, top_k=5):
    started_at = time.monotonic()
    retrieval_results = retrieve(query=question, filters=filters, top_k=top_k)
    retrieval_payload = build_retrieval_response(query=question, results=retrieval_results)
    citations = retrieval_payload["citations"]
    duration_ms = int((time.monotonic() - started_at) * 1000)
    return {
        "question": question,
        "query": question,
        "messages": _build_messages(question, citations),
        "citations": citations,
        "answer_mode": "cited" if citations else "fallback",
        "answer_notice": _build_answer_notice(citations),
        "duration_ms": duration_ms,
        "retrieval_results": retrieval_results,
        "filters": filters or {},
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


def ask_question(*, question, filters=None, top_k=5):
    payload = _prepare_answer(question, filters=filters, top_k=top_k)
    answer = get_chat_provider().chat(messages=payload["messages"])
    _record_retrieval_log(payload)
    return {
        "question": payload["question"],
        "query": payload["query"],
        "answer": answer,
        "citations": payload["citations"],
        "answer_mode": payload["answer_mode"],
        "answer_notice": payload["answer_notice"],
        "duration_ms": payload["duration_ms"],
    }


def stream_question(*, question, filters=None, top_k=5):
    payload = _prepare_answer(question, filters=filters, top_k=top_k)
    provider = get_chat_provider()

    def event_stream():
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

        answer = "".join(chunks)
        _record_retrieval_log(payload)
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
