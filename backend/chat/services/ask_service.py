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


def _build_answer(question, citations):
    if not citations:
        return f"针对“{question}”，当前知识库中未检索到相关资料，无法生成基于引用的回答。"

    prompt = render_prompt(
        "chat/answer.txt",
        question=question,
        context=_build_context(citations),
    )
    provider = get_chat_provider()
    return provider.chat(
        messages=[
            {
                "role": "user",
                "content": prompt,
            }
        ]
    )


def ask_question(*, question, filters=None, top_k=5):
    started_at = time.monotonic()
    retrieval_results = retrieve(query=question, filters=filters, top_k=top_k)
    retrieval_payload = build_retrieval_response(query=question, results=retrieval_results)
    citations = retrieval_payload["citations"]
    response_payload = {
        "question": question,
        "query": question,
        "answer": _build_answer(question, citations),
        "citations": citations,
    }
    create_retrieval_log(
        query=question,
        top_k=top_k,
        filters=filters or {},
        results=retrieval_results,
        source=RetrievalLog.SOURCE_CHAT_ASK,
        duration_ms=int((time.monotonic() - started_at) * 1000),
    )
    return response_payload
